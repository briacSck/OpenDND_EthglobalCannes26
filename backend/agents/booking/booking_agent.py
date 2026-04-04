"""Booking agent — headless browser automation for activity reservations.

Pipeline: Discovery → Availability Check → Multi-step Navigation → Confirmation.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import uuid

from config import DEMO_MODE

from agents.booking.models import (
    BookingFormData,
    BookingIntent,
    BookingResult,
    NavigationResult,
)
from agents.quest_generation.models import ActivityRef

logger = logging.getLogger(__name__)

_BOOKING_TIMEOUT_SECONDS = 45  # hard wall-clock limit for the entire automated path


async def prepare_booking_from_activity(
    activity: ActivityRef,
    quest_location: str,
    desired_datetime: str = "",
    guest_count: int = 1,
    budget_eur: float = 50,
) -> BookingIntent | None:
    """Adapter: map an ActivityRef from quest generation to a BookingIntent.

    Returns None for narrative-only steps (no concrete activity).
    When booking_url is empty, attempts proactive web discovery.
    """
    if not activity.name:
        return None

    url = activity.booking_url

    # Proactive discovery when URL is missing
    if not url:
        from agents.booking.web_discovery import find_booking_url

        url = await find_booking_url(
            activity.name,
            quest_location,
            desired_datetime,
            guest_count,
            budget_eur or activity.price_eur,
        )

    if not url:
        return None

    return await prepare_booking(
        activity_name=activity.name,
        location=activity.address or quest_location,
        url=url,
        budget_eur=activity.price_eur or budget_eur,
    )


async def prepare_booking(
    activity_name: str,
    location: str,
    url: str | None,
    budget_eur: float,
) -> BookingIntent:
    """Navigate to the booking page and assess what is needed.

    In DEMO_MODE: returns a mock BookingIntent instantly.
    In real mode: uses Playwright (headless) to inspect the checkout flow.
    """
    if DEMO_MODE:
        return BookingIntent(
            activity_name=activity_name,
            booking_url=url or f"https://example.com/book/{activity_name.lower().replace(' ', '-')}",
            price_eur=min(budget_eur, 25.0),
            steps_to_complete=["select date", "choose guests", "confirm"],
            requires_human_action=True,
            reason="DEMO_MODE — payment form requires human completion",
        )

    if not url:
        return BookingIntent(
            activity_name=activity_name,
            booking_url="",
            price_eur=0,
            steps_to_complete=[],
            requires_human_action=True,
            reason=f"No booking URL available for {activity_name}",
        )

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("playwright not installed — falling back to URL-only intent")
        return BookingIntent(
            activity_name=activity_name,
            booking_url=url,
            price_eur=budget_eur,
            steps_to_complete=["open booking page", "complete checkout manually"],
            requires_human_action=True,
            reason="Playwright not available for automated inspection",
        )

    steps_found: list[str] = []
    requires_human = True
    reason = None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=15_000, wait_until="domcontentloaded")

            # Detect common checkout blockers
            has_payment = await page.locator(
                "input[name*='card'], input[name*='payment'], iframe[src*='stripe'], iframe[src*='paypal']"
            ).count()
            has_captcha = await page.locator(
                "iframe[src*='captcha'], iframe[src*='recaptcha'], .g-recaptcha, .h-captcha"
            ).count()
            has_login = await page.locator(
                "input[type='password'], form[action*='login'], form[action*='signin']"
            ).count()

            steps_found.append("open booking page")

            if has_login:
                steps_found.append("login required")
                reason = "Login wall detected"
            if has_captcha:
                steps_found.append("solve CAPTCHA")
                reason = (reason + " + CAPTCHA" if reason else "CAPTCHA detected")
            if has_payment:
                steps_found.append("enter payment details")
                reason = (reason + " + payment form" if reason else "Payment form detected")

            if not has_payment and not has_captcha and not has_login:
                steps_found.append("fill booking form")
                steps_found.append("confirm reservation")
                requires_human = False

        except Exception as exc:
            logger.warning("Playwright navigation failed for %s: %s", url, exc)
            steps_found = ["open booking page manually"]
            reason = f"Page load failed: {exc}"
        finally:
            await browser.close()

    return BookingIntent(
        activity_name=activity_name,
        booking_url=url,
        price_eur=budget_eur,
        steps_to_complete=steps_found,
        requires_human_action=requires_human,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Navigation system prompt for the ReAct loop
# ---------------------------------------------------------------------------

NAVIGATION_SYSTEM_PROMPT = """\
You are a booking automation agent. You observe a web page and decide what \
action to take next to complete a booking.

Available actions (return as JSON, no markdown fences):
- {"type": "fill", "selector": "<css>", "value": "<text>"}
- {"type": "click", "selector": "<css>"}
- {"type": "select", "selector": "<css>", "value": "<option value or text>"}
- {"type": "done", "booking_ref": "<extracted reference if visible>"}
- {"type": "stuck", "reason": "<why you can't proceed>"}

Rules:
- Fill fields with the booking data provided (name, email, date, guests).
- For date pickers: prefer input[type="date"] with YYYY-MM-DD format.
- For calendar widgets: click the target date button/cell.
- Click "Next", "Continue", "Réserver", "Book", "Confirm" to advance.
- If you see a confirmation page ("confirmed", "thank you", "merci") → "done".
- If you see a login wall, CAPTCHA, or payment form → "stuck".
- Use the most specific CSS selector possible.
- Return exactly ONE action per turn as a JSON object.
"""


# ---------------------------------------------------------------------------
# ReAct helpers
# ---------------------------------------------------------------------------


async def _extract_page_summary(page) -> str:
    """Extract a simplified DOM representation for LLM reasoning."""
    try:
        summary = await page.evaluate(
            """() => {
            const parts = [];
            parts.push('Title: ' + document.title);

            // Forms and their inputs
            const inputs = document.querySelectorAll(
                'input, select, textarea, button[type="submit"]'
            );
            if (inputs.length) {
                parts.push('\\nForm fields:');
                inputs.forEach(el => {
                    if (!el.offsetParent) return; // skip hidden
                    const tag = el.tagName.toLowerCase();
                    const type = el.type || '';
                    const name = el.name || el.id || '';
                    const lbl = el.labels && el.labels[0]
                        ? el.labels[0].textContent.trim().slice(0, 60)
                        : (el.placeholder || el.getAttribute('aria-label') || '');
                    const val = el.value || '';
                    parts.push(
                        '  <' + tag + ' type="' + type + '" name="' + name
                        + '" label="' + lbl + '" value="' + val + '">'
                    );
                });
            }

            // Standalone buttons / links
            const btns = document.querySelectorAll(
                'button:not(form button), a[class*="btn"], a[class*="book"], '
                + 'a[class*="reserve"], a[class*="réserv"]'
            );
            if (btns.length) {
                parts.push('\\nButtons:');
                btns.forEach(el => {
                    if (!el.offsetParent) return;
                    parts.push(
                        '  "' + el.textContent.trim().slice(0, 50)
                        + '" [' + (el.className || '').slice(0, 40) + ']'
                    );
                });
            }

            // Visible text excerpt
            const body = document.body.innerText.slice(0, 2000);
            parts.push('\\nVisible text (first 2000 chars):\\n' + body);

            return parts.join('\\n');
        }"""
        )
        return summary[:4000]
    except Exception as exc:
        return f"(page summary extraction failed: {exc})"


async def _extract_page_summary_with_screenshot(page) -> str:
    """Fallback: screenshot + vision when DOM extraction yields no form fields."""
    dom = await _extract_page_summary(page)
    if "Form fields:" in dom:
        return dom

    # DOM was empty/useless — use screenshot via vision
    try:
        from integrations.compute.compute_client import compute_client

        screenshot_bytes = await page.screenshot(full_page=False)
        b64 = base64.b64encode(screenshot_bytes).decode()

        response = await compute_client.create_message(
            system=(
                "Describe this booking page. List all visible form fields, "
                "dropdowns, date pickers, buttons, and key information."
            ),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Describe every input field, dropdown, button, "
                                "and date/time widget on this booking page."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
        vision_text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                vision_text += block.text
        return f"{dom}\n\n--- Screenshot description ---\n{vision_text}"
    except Exception as exc:
        logger.warning("Vision fallback failed: %s", exc)
        return dom


def _parse_action(response) -> dict:
    """Parse an LLM response into an action dict. Best-effort."""
    text = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            text += block.text

    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object in the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {"type": "stuck", "reason": "Could not parse LLM action"}


async def _execute_action(page, action: dict) -> str:
    """Execute a single Playwright action. Returns a short result string."""
    action_type = action.get("type", "")
    selector = action.get("selector", "")

    try:
        if action_type == "fill" and selector:
            await page.locator(selector).first.fill(
                action.get("value", ""), timeout=3000
            )
            return "filled"
        elif action_type == "click" and selector:
            await page.locator(selector).first.click(timeout=3000)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass  # page may not navigate
            return "clicked"
        elif action_type == "select" and selector:
            await page.locator(selector).first.select_option(
                action.get("value", ""), timeout=3000
            )
            return "selected"
        elif action_type in ("done", "stuck"):
            return action_type
        else:
            return f"unknown action: {action_type}"
    except Exception as exc:
        return f"failed: {exc}"


async def _detect_confirmation(page) -> bool:
    """Check if the current page is a booking confirmation."""
    url_lower = page.url.lower()
    if any(
        kw in url_lower
        for kw in ["confirm", "success", "merci", "thank", "done", "receipt", "complete"]
    ):
        return True

    try:
        body = (await page.inner_text("body")).lower()
    except Exception:
        return False

    confirm_phrases = [
        "confirmed", "confirmation", "successfully", "thank you",
        "your booking", "merci", "votre réservation",
        "réservation confirmée", "c'est réservé", "booking reference",
        "numéro de réservation",
    ]
    return any(phrase in body for phrase in confirm_phrases)


async def _detect_blocker(page) -> bool:
    """Check if the page has a login wall, CAPTCHA, or payment form."""
    checks = [
        "input[type='password'], form[action*='login'], form[action*='signin']",
        "iframe[src*='captcha'], iframe[src*='recaptcha'], .g-recaptcha, .h-captcha",
        "input[name*='card'], iframe[src*='stripe'], iframe[src*='paypal']",
    ]
    for selector in checks:
        try:
            if await page.locator(selector).count():
                return True
        except Exception:
            pass
    return False


async def _extract_booking_ref(page) -> str | None:
    """Try to extract a booking reference number from the page text."""
    try:
        body = await page.inner_text("body")
    except Exception:
        return None
    match = re.search(
        r"(?:ref|reference|booking|confirmation|numéro|n°)"
        r"[^\w]*[:#\s]*([A-Z0-9][\w-]{3,20})",
        body,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# navigate_booking_flow — LLM-driven multi-step ReAct loop
# ---------------------------------------------------------------------------


async def navigate_booking_flow(
    page,
    form_data: BookingFormData,
    max_steps: int = 6,
) -> NavigationResult:
    """LLM-driven multi-step booking navigation.

    At each step: extract page state → ask LLM what to do → execute → loop.
    """
    if DEMO_MODE:
        return NavigationResult(
            success=True,
            booking_ref=f"DEMO-{uuid.uuid4().hex[:8].upper()}",
            final_url=page.url,
        )

    from integrations.compute.compute_client import compute_client

    steps_log: list[str] = []
    prev_urls: list[str] = []
    consecutive_failures = 0

    for step_num in range(max_steps):
        # 1. Check for confirmation
        if await _detect_confirmation(page):
            ref = await _extract_booking_ref(page)
            logger.info("Booking confirmed at step %d: %s", step_num, page.url)
            return NavigationResult(
                success=True,
                final_url=page.url,
                booking_ref=ref,
                steps_taken=steps_log,
            )

        # 2. Check for blocker
        if step_num > 0 and await _detect_blocker(page):
            return NavigationResult(
                success=False,
                final_url=page.url,
                reason="login, CAPTCHA, or payment form detected",
                steps_taken=steps_log,
            )

        # 3. Observe — extract page state
        dom_summary = await _extract_page_summary_with_screenshot(page)

        # 4. Reason — ask LLM
        booking_info = (
            f"name={form_data.player_name}, "
            f"email={form_data.player_email}, "
            f"date={form_data.datetime_str}, "
            f"guests={form_data.guest_count}"
        )
        user_content = (
            f"Step {step_num + 1}/{max_steps}.\n"
            f"Page URL: {page.url}\n\n"
            f"Page summary:\n{dom_summary}\n\n"
            f"Booking data: {booking_info}\n"
            f"Previous actions: {steps_log[-3:] if steps_log else 'none'}\n\n"
            f"What single action should I take next?"
        )

        try:
            response = await compute_client.create_message(
                system=NAVIGATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
                max_tokens=500,
            )
            action = _parse_action(response)
        except Exception as exc:
            logger.warning("LLM reasoning failed at step %d: %s", step_num, exc)
            steps_log.append(f"step {step_num}: LLM error — {exc}")
            consecutive_failures += 1
            if consecutive_failures >= 2:
                break
            continue

        logger.info(
            "Booking ReAct step %d/%d: %s on %s",
            step_num + 1, max_steps, action.get("type"), page.url,
        )

        # 5. Act
        if action.get("type") == "done":
            ref = action.get("booking_ref") or await _extract_booking_ref(page)
            return NavigationResult(
                success=True,
                final_url=page.url,
                booking_ref=ref,
                steps_taken=steps_log,
            )

        if action.get("type") == "stuck":
            return NavigationResult(
                success=False,
                final_url=page.url,
                reason=action.get("reason", "LLM reported stuck"),
                steps_taken=steps_log,
            )

        result = await _execute_action(page, action)
        step_desc = (
            f"step {step_num}: {action.get('type')} "
            f"{action.get('selector', '')[:40]} → {result}"
        )
        steps_log.append(step_desc)

        if result.startswith("failed"):
            consecutive_failures += 1
            if consecutive_failures >= 3:
                return NavigationResult(
                    success=False,
                    final_url=page.url,
                    reason=f"3 consecutive action failures: {result}",
                    steps_taken=steps_log,
                )
        else:
            consecutive_failures = 0

        # Detect infinite loop (same URL clicked 3 times)
        prev_urls.append(page.url)
        if len(prev_urls) >= 3 and len(set(prev_urls[-3:])) == 1 and step_num >= 2:
            same_actions = [s for s in steps_log[-3:] if "click" in s]
            if len(same_actions) >= 3:
                return NavigationResult(
                    success=False,
                    final_url=page.url,
                    reason="navigation loop detected",
                    steps_taken=steps_log,
                )

    # Max steps exhausted
    if await _detect_confirmation(page):
        ref = await _extract_booking_ref(page)
        return NavigationResult(
            success=True, final_url=page.url, booking_ref=ref, steps_taken=steps_log,
        )

    return NavigationResult(
        success=False,
        final_url=page.url,
        reason=f"max steps ({max_steps}) reached without confirmation",
        steps_taken=steps_log,
    )


# ---------------------------------------------------------------------------
# complete_booking — public API, wraps the full pipeline
# ---------------------------------------------------------------------------


async def complete_booking(
    intent: BookingIntent,
    form_data: BookingFormData | None = None,
) -> BookingResult:
    """Attempt to complete the booking using the LLM-driven navigation pipeline.

    In DEMO_MODE: returns a mock completed result.
    If requires_human_action: returns pending_human with instructions.
    Otherwise: runs the automated pipeline under a wall-clock timeout.
    """
    if DEMO_MODE:
        return BookingResult(
            status="completed",
            booking_ref=f"DEMO-{uuid.uuid4().hex[:8].upper()}",
            confirmation_url=intent.booking_url,
            instructions=None,
        )

    if intent.requires_human_action:
        return BookingResult(
            status="pending_human",
            booking_ref=None,
            confirmation_url=intent.booking_url or None,
            instructions=f"Please complete booking at {intent.booking_url}"
            + (f" — {intent.reason}" if intent.reason else ""),
        )

    try:
        return await asyncio.wait_for(
            _run_automated_booking(intent, form_data or BookingFormData()),
            timeout=_BOOKING_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Booking timed out after %ds for %s",
            _BOOKING_TIMEOUT_SECONDS,
            intent.activity_name,
        )
        return BookingResult(
            status="pending_human",
            confirmation_url=intent.booking_url,
            instructions=(
                f"Automated booking timed out. "
                f"Please complete at {intent.booking_url}"
            ),
        )


async def _run_automated_booking(
    intent: BookingIntent,
    form_data: BookingFormData,
) -> BookingResult:
    """The actual Playwright pipeline — called inside asyncio.wait_for()."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return BookingResult(
            status="failed",
            instructions="Playwright not available for automated booking",
        )

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(
                    intent.booking_url, timeout=15_000, wait_until="domcontentloaded"
                )

                # Step 1: availability check on the already-open page
                from agents.booking.web_discovery import check_availability

                avail = await check_availability(
                    page, form_data.datetime_str, form_data.guest_count
                )
                if not avail.available and avail.reason:
                    alt = (
                        f" Try: {', '.join(avail.available_slots[:3])}"
                        if avail.available_slots
                        else ""
                    )
                    return BookingResult(
                        status="failed",
                        confirmation_url=page.url,
                        instructions=f"Not available: {avail.reason}.{alt}",
                    )

                # Step 2: LLM-driven multi-step navigation
                nav_result = await navigate_booking_flow(page, form_data, max_steps=6)

                if nav_result.success:
                    return BookingResult(
                        status="completed",
                        booking_ref=(
                            nav_result.booking_ref
                            or f"AUTO-{uuid.uuid4().hex[:8].upper()}"
                        ),
                        confirmation_url=nav_result.final_url,
                    )
                else:
                    is_human_blocker = any(
                        kw in (nav_result.reason or "")
                        for kw in ("login", "payment", "CAPTCHA")
                    )
                    return BookingResult(
                        status="pending_human" if is_human_blocker else "failed",
                        booking_ref=None,
                        confirmation_url=nav_result.final_url or page.url,
                        instructions=(
                            f"I got as far as I could automatically! "
                            f"Complete your booking here: "
                            f"{nav_result.final_url or page.url}"
                        ),
                    )
            finally:
                await browser.close()

    except Exception as exc:
        logger.warning(
            "Booking pipeline failed for %s: %s", intent.activity_name, exc
        )
        return BookingResult(
            status="failed",
            instructions=(
                f"Booking failed: {exc}. "
                f"Complete manually at {intent.booking_url}"
            ),
        )

"""Booking agent — headless browser automation for activity reservations."""

from __future__ import annotations

import logging
import uuid

from config import DEMO_MODE

from agents.booking.models import BookingIntent, BookingResult

logger = logging.getLogger(__name__)


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


async def complete_booking(intent: BookingIntent) -> BookingResult:
    """Attempt to complete the booking based on the prepared intent.

    In DEMO_MODE: returns a mock completed result.
    If requires_human_action: returns pending_human with instructions.
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

    # Automated completion path (no login, no CAPTCHA, no payment form)
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
                # Attempt to find and click the primary submit/confirm button
                confirm_btn = page.locator(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Book'), button:has-text('Confirm'), "
                    "button:has-text('Reserve'), button:has-text('Réserver')"
                ).first
                if await confirm_btn.count():
                    await confirm_btn.click(timeout=5_000)
                    await page.wait_for_load_state("domcontentloaded", timeout=10_000)

                final_url = page.url
                return BookingResult(
                    status="completed",
                    booking_ref=f"AUTO-{uuid.uuid4().hex[:8].upper()}",
                    confirmation_url=final_url,
                )
            finally:
                await browser.close()

    except Exception as exc:
        logger.warning("Automated booking failed for %s: %s", intent.activity_name, exc)
        return BookingResult(
            status="failed",
            instructions=f"Automated booking failed: {exc}. "
            f"Please complete manually at {intent.booking_url}",
        )

"""Web discovery — proactive search for booking URLs and availability checking.

When ActivityRef.booking_url is empty, this module searches the web to find
real bookable options, then optionally checks availability on the target page.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

from config import DEMO_MODE

from agents.booking.models import AvailabilityResult, BookingOption

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Discover booking options
# ---------------------------------------------------------------------------


async def discover_booking_options(
    activity_name: str,
    location: str,
    desired_datetime: str = "",
    guest_count: int = 1,
    budget_eur: float = 50,
) -> list[BookingOption]:
    """Search the web for bookable activity options.

    Strategy A: platform-specific scrapers (reusing city_research/tools.py).
    Strategy B: LLM synthesis to rank and extract structured options.
    """
    if DEMO_MODE:
        slug = activity_name.lower().replace(" ", "-")
        return [
            BookingOption(
                name=f"Demo: {activity_name}",
                url=f"https://example.com/book/{slug}",
                price_eur=min(budget_eur * 0.6, 25.0),
                source="demo",
                score=1.0,
            )
        ]

    from agents.city_research.tools import (
        search_getyourguide,
        search_google,
        search_tripadvisor,
    )

    # --- Strategy A: platform scrapers ---
    raw_parts: dict[str, str] = {}

    for label, coro in [
        ("getyourguide", search_getyourguide(activity_name, location)),
        ("tripadvisor", search_tripadvisor(activity_name, location)),
        (
            "google",
            search_google(
                f"{activity_name} {location} réserver "
                "site:viator.com OR site:getyourguide.com "
                "OR site:airbnb.com OR réservation"
            ),
        ),
    ]:
        try:
            raw_parts[label] = await coro
        except Exception as exc:
            logger.warning("Discovery search %s failed: %s", label, exc)
            raw_parts[label] = ""

    combined = "\n\n".join(
        f"--- {src} ---\n{text}" for src, text in raw_parts.items() if text
    )

    if not combined.strip():
        return []

    # --- Strategy B: LLM synthesis ---
    try:
        from integrations.compute.compute_client import compute_client

        response = await compute_client.create_message(
            system=(
                "You are a booking research assistant. "
                "Extract the best booking options from search results. "
                "Return ONLY a JSON array — no markdown fences, no explanation."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Find booking options for '{activity_name}' in {location}, "
                        f"{guest_count} people, {desired_datetime or 'flexible date'}, "
                        f"budget {budget_eur}€.\n\n"
                        f"Search results:\n{combined[:6000]}\n\n"
                        "Return a JSON array of objects with keys: "
                        "name (str), url (str), price_eur (number|null), "
                        "source (str), score (float 0-1). "
                        "Only include entries with a real direct booking URL "
                        "(https://...). Score by relevance to the request."
                    ),
                }
            ],
            max_tokens=2000,
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                text += block.text

        options = _parse_options_json(text)
        if options:
            return sorted(options, key=lambda o: o.score, reverse=True)
    except Exception as exc:
        logger.warning("LLM synthesis failed for discovery: %s", exc)

    # --- Fallback: regex URL extraction from raw results ---
    return _extract_urls_from_raw(combined, activity_name)


def _parse_options_json(text: str) -> list[BookingOption]:
    """Best-effort parse of LLM JSON response into BookingOption list."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON array in the text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return []

    if not isinstance(data, list):
        return []

    options = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "")
        if not url or not url.startswith("http"):
            continue
        options.append(
            BookingOption(
                name=item.get("name", "Unknown"),
                url=url,
                price_eur=item.get("price_eur"),
                source=item.get("source", ""),
                score=float(item.get("score", 0.5)),
            )
        )
    return options


def _extract_urls_from_raw(text: str, activity_name: str) -> list[BookingOption]:
    """Fallback: regex-extract booking URLs from raw search results."""
    url_pattern = re.compile(
        r"https?://(?:www\.)?(?:getyourguide\.\w+|viator\.com|airbnb\.\w+|"
        r"eventbrite\.\w+|booking\.com|tripadvisor\.\w+)/\S+"
    )
    seen: set[str] = set()
    options = []
    for match in url_pattern.finditer(text):
        url = match.group().rstrip(".,;)\"'")
        if url in seen:
            continue
        seen.add(url)
        options.append(
            BookingOption(
                name=activity_name,
                url=url,
                source="regex_fallback",
                score=0.3,
            )
        )
    return options[:5]


# ---------------------------------------------------------------------------
# 2. Convenience wrapper
# ---------------------------------------------------------------------------


async def find_booking_url(
    activity_name: str,
    location: str,
    desired_datetime: str = "",
    guest_count: int = 1,
    budget_eur: float = 50,
) -> str | None:
    """Return the best booking URL, or None if nothing found."""
    options = await discover_booking_options(
        activity_name, location, desired_datetime, guest_count, budget_eur
    )
    return options[0].url if options else None


# ---------------------------------------------------------------------------
# 3. Availability checking
# ---------------------------------------------------------------------------


async def check_availability(
    page,
    desired_datetime: str,
    guest_count: int,
) -> AvailabilityResult:
    """Read availability from an already-loaded Playwright page. No navigation.

    Inspects the DOM for date/time selectors, sold-out indicators, and guest
    capacity limits. Best-effort — returns available=True when unsure.
    """
    try:
        body_text = await page.inner_text("body")
    except Exception:
        return AvailabilityResult(available=True, reason="could not read page")

    body_lower = body_text.lower()

    # Check for sold-out / unavailable indicators
    unavailable_phrases = [
        "sold out", "complet", "unavailable", "no availability",
        "plus de places", "épuisé", "not available", "fully booked",
        "aucun créneau", "no slots",
    ]
    for phrase in unavailable_phrases:
        if phrase in body_lower:
            return AvailabilityResult(
                available=False,
                reason=f"Page indicates unavailability: '{phrase}'",
            )

    # Check for login/payment blockers
    has_login = await page.locator(
        "input[type='password'], form[action*='login'], form[action*='signin']"
    ).count()
    has_payment = await page.locator(
        "input[name*='card'], iframe[src*='stripe'], iframe[src*='paypal']"
    ).count()
    if has_login or has_payment:
        return AvailabilityResult(
            available=False,
            needs_human=True,
            reason="login or payment required before viewing availability",
        )

    # Try to read available time slots
    available_slots: list[str] = []
    try:
        slot_elements = page.locator(
            "button[class*='slot'], [class*='time-slot'], "
            "[class*='timeslot'], [data-time], "
            "select[name*='time'] option, select[name*='heure'] option"
        )
        count = await slot_elements.count()
        for i in range(min(count, 10)):
            text = (await slot_elements.nth(i).inner_text()).strip()
            if text and len(text) < 30:
                available_slots.append(text)
    except Exception:
        pass

    # Try to extract price
    price_confirmed = None
    try:
        price_el = page.locator(
            "[class*='price'], [class*='Price'], [class*='total'], [class*='Total']"
        ).first
        if await price_el.count():
            price_text = await price_el.inner_text()
            price_match = re.search(r"(\d+[.,]?\d*)\s*€", price_text)
            if price_match:
                price_confirmed = float(price_match.group(1).replace(",", "."))
    except Exception:
        pass

    return AvailabilityResult(
        available=True,
        available_slots=available_slots,
        price_confirmed=price_confirmed,
        reason="" if available_slots else "no calendar detected — assuming available",
    )


async def check_availability_url(
    url: str,
    desired_datetime: str,
    guest_count: int,
) -> AvailabilityResult:
    """Open a page, check availability, close. For pre-flight checks."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return AvailabilityResult(available=True, reason="playwright not installed")

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=15_000, wait_until="domcontentloaded")
                return await check_availability(page, desired_datetime, guest_count)
            finally:
                await browser.close()
    except Exception as exc:
        return AvailabilityResult(available=True, reason=f"check failed: {exc}")

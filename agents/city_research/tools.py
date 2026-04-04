"""Search tools for the City Research Agent.

Each tool scrapes/searches a specific source and returns raw text results.
Claude will parse and structure these results into the CityContext models.
"""

from __future__ import annotations

import json
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

TIMEOUT = 15.0


async def search_google(query: str) -> str:
    """Search the web using DuckDuckGo HTML (no API key needed, no CAPTCHA)."""
    url = "https://html.duckduckgo.com/html/"
    data = {"q": query}
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.post(url, data=data)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for r in soup.select(".result"):
        title_el = r.select_one(".result__a")
        snippet_el = r.select_one(".result__snippet")
        title = title_el.get_text(strip=True) if title_el else ""
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        link = ""
        if title_el and title_el.get("href"):
            link = title_el["href"]
        if title:
            results.append(f"**{title}**\n{snippet}\n{link}")
    return "\n\n".join(results[:10]) if results else f"No results found for: {query}"


async def search_tripadvisor(query: str, location: str) -> str:
    """Search TripAdvisor for activities/restaurants in a location."""
    search_query = f"site:tripadvisor.fr {query} {location}"
    return await search_google(search_query)


async def search_google_maps(query: str, location: str, radius_km: float = 3.0) -> str:
    """Search Google Maps for places near a location."""
    search_query = f"{query} near {location} within {radius_km}km"
    return await search_google(search_query)


async def search_luma(query: str, location: str) -> str:
    """Search Luma for events in a location."""
    search_query = f"site:lu.ma {query} {location}"
    google_results = await search_google(search_query)

    # Also try Luma's explore page
    luma_results = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(f"https://lu.ma/explore?query={query}+{location}")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for card in soup.select("[class*='event-card'], [class*='EventCard']"):
                    text = card.get_text(separator=" | ", strip=True)
                    if text:
                        luma_results.append(text)
    except Exception:
        pass

    parts = [google_results]
    if luma_results:
        parts.append("--- Luma direct results ---\n" + "\n".join(luma_results[:10]))
    return "\n\n".join(parts)


async def search_getyourguide(query: str, location: str) -> str:
    """Search GetYourGuide for bookable activities."""
    search_query = f"site:getyourguide.fr {query} {location}"
    google_results = await search_google(search_query)

    # Also try GYG directly
    gyg_results = []
    try:
        search_url = f"https://www.getyourguide.fr/s/?q={query}+{location}"
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(search_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for card in soup.select("[data-activity-card], .activity-card, article"):
                    title = card.select_one("h3, h2, [class*='title']")
                    price = card.select_one("[class*='price'], [class*='Price']")
                    rating = card.select_one("[class*='rating'], [class*='Rating']")
                    parts = []
                    if title:
                        parts.append(title.get_text(strip=True))
                    if price:
                        parts.append(f"Price: {price.get_text(strip=True)}")
                    if rating:
                        parts.append(f"Rating: {rating.get_text(strip=True)}")
                    if parts:
                        gyg_results.append(" | ".join(parts))
    except Exception:
        pass

    results = [google_results]
    if gyg_results:
        results.append("--- GetYourGuide direct results ---\n" + "\n".join(gyg_results[:10]))
    return "\n\n".join(results)


async def get_weather(location: str, date: str) -> str:
    """Get weather forecast for a location and date."""
    search_query = f"weather {location} {date}"
    return await search_google(search_query)


async def get_directions(origin: str, destination: str) -> str:
    """Get walking directions between two points using OSRM (real walking distances)."""
    # First, geocode both locations via Nominatim
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
        coords = []
        for place in [origin, destination]:
            try:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": place, "format": "json", "limit": 1},
                    headers={"User-Agent": "OpenDnD-QuestGen/1.0"},
                )
                data = resp.json()
                if data:
                    coords.append((float(data[0]["lon"]), float(data[0]["lat"])))
                else:
                    # Fallback to Google search if geocoding fails
                    return await search_google(f"walking distance {origin} to {destination} travel time")
            except Exception:
                return await search_google(f"walking distance {origin} to {destination} travel time")

        if len(coords) != 2:
            return await search_google(f"walking distance {origin} to {destination} travel time")

        # Call OSRM for walking route
        try:
            osrm_url = f"http://router.project-osrm.org/route/v1/foot/{coords[0][0]},{coords[0][1]};{coords[1][0]},{coords[1][1]}?overview=false"
            resp = await client.get(osrm_url)
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                distance_m = route["distance"]
                duration_s = route["duration"]
                distance_km = distance_m / 1000
                duration_min = duration_s / 60
                return (
                    f"Walking directions: {origin} → {destination}\n"
                    f"Distance: {distance_km:.1f} km ({distance_m:.0f} m)\n"
                    f"Walking time: {duration_min:.0f} minutes\n"
                    f"Source: OSRM (OpenStreetMap)"
                )
        except Exception:
            pass

    # Fallback
    return await search_google(f"walking distance {origin} to {destination} travel time")


async def search_news(query: str, location: str) -> str:
    """Search for current news, scandals, geopolitical events related to a location."""
    results = []
    # Local news
    local = await search_google(f"news {location} {query} 2026")
    results.append(f"--- Local news ---\n{local}")
    # Broader geopolitical / scandal / events
    broader = await search_google(f"{query} {location} scandal conference summit affair 2026")
    results.append(f"--- Geopolitical context ---\n{broader}")
    return "\n\n".join(results)


# --- Tool definitions for Claude API tool_use ---

TOOL_DEFINITIONS = [
    {
        "name": "search_google",
        "description": "Search Google for general information. Use for weather, city info, transport, or any generic query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_tripadvisor",
        "description": "Search TripAdvisor for activities, restaurants, and things to do in a location. Great for ratings and reviews.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for (e.g. 'cours de boxe', 'restaurant japonais')"},
                "location": {"type": "string", "description": "City or neighborhood (e.g. 'Cannes', 'Paris Marais')"},
            },
            "required": ["query", "location"],
        },
    },
    {
        "name": "search_google_maps",
        "description": "Search Google Maps for places near a location. Good for finding specific venues, addresses, and distances.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "location": {"type": "string", "description": "City or neighborhood"},
                "radius_km": {"type": "number", "description": "Search radius in km (default 3)", "default": 3.0},
            },
            "required": ["query", "location"],
        },
    },
    {
        "name": "search_luma",
        "description": "Search Luma (lu.ma) for upcoming events in a location. Great for finding local meetups, parties, and social events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Event type or keywords"},
                "location": {"type": "string", "description": "City or neighborhood"},
            },
            "required": ["query", "location"],
        },
    },
    {
        "name": "search_getyourguide",
        "description": "Search GetYourGuide for bookable activities and tours. Returns prices and availability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Activity type or keywords"},
                "location": {"type": "string", "description": "City or neighborhood"},
            },
            "required": ["query", "location"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get weather forecast for a location on a specific date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "date": {"type": "string", "description": "Date (e.g. '2026-04-05')"},
            },
            "required": ["location", "date"],
        },
    },
    {
        "name": "get_directions",
        "description": "Get walking/transit time between two places.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Starting point (address or place name)"},
                "destination": {"type": "string", "description": "Destination (address or place name)"},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "search_news",
        "description": "Search for current news, scandals, geopolitical events, conferences, judicial affairs related to a location. Use for high_stakes quests to anchor narratives in reality.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "News topic or keywords (e.g. 'crypto scandal', 'diplomatic summit', 'art theft')"},
                "location": {"type": "string", "description": "City or region"},
            },
            "required": ["query", "location"],
        },
    },
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "search_google": search_google,
    "search_tripadvisor": search_tripadvisor,
    "search_google_maps": search_google_maps,
    "search_luma": search_luma,
    "search_getyourguide": search_getyourguide,
    "get_weather": get_weather,
    "get_directions": get_directions,
    "search_news": search_news,
}

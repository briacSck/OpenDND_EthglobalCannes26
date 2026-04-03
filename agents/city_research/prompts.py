"""System prompts for the City Research Agent."""

CITY_RESEARCH_SYSTEM_PROMPT = """\
You are the City Research Agent for OpenD&D — an AI system that creates real-life narrative quests.

Your job: research a city to find REAL places, activities, events, and restaurants that will become the building blocks of an epic quest.

## How you work

You receive a quest request with: goal, vibe, duration, budget, location, difficulty, players count, and datetime.

You then perform iterative research:

### Pass 0 — City Factsheet
Before searching for specific activities, compile a LONG and DETAILED factual briefing about the city (800-1500 words). This is raw reference material for the Quest Writer — do NOT romanticize or narrate. Just pack in as many useful facts as possible. Structure it as:

- **History**: founding date, key historical periods, major events, wars, rulers, famous historical figures born or linked to the city
- **Geography & climate**: exact location, elevation, coastline, rivers, mountains nearby, neighborhoods and their character, typical weather by season
- **Demographics & culture**: population, languages, local traditions, festivals, patron saint, local cuisine and signature dishes, cultural identity
- **Architecture & landmarks**: major monuments, churches, museums, fortifications, notable buildings, parks, plazas
- **Economy & modern life**: main industries, port/airport, universities, sports teams, what the city is known for today
- **Dark history & mysteries**: local legends, ghost stories, famous crimes, unsolved mysteries, hidden underground, secret passages
- **Famous people**: actors, writers, artists, politicians linked to the city
- **Local quirks**: unusual laws, local slang, neighborhood rivalries, things only locals know

Write in French. Be FACTUAL and EXHAUSTIVE. No flowery prose — just dense, useful information. The Quest Writer will use this as raw material to craft narratives.

### Pass 1b — Current News & Geopolitical Context (HIGH_STAKES only)
If the quest tone is "high_stakes", you MUST also research current news to anchor the narrative in reality:
- **Local news**: recent scandals, judicial affairs, investigations, political events in the city
- **Conferences & summits**: any major conferences, diplomatic events, tech summits happening in the region
- **Art/heritage crimes**: thefts, forgeries, mysterious discoveries, archaeological finds
- **Geopolitical context**: international tensions, diplomatic incidents, espionage cases that could tie to the location
- **Financial scandals**: fraud, money laundering, crypto schemes linked to the area
- Use the `search_news` tool for these queries.
- Find at least 5-10 real, verifiable news items. The player must be able to Google them and find real articles.
- For each news item, note WHY it could be woven into a spy/thriller/Da Vinci Code narrative.

### Pass 1 — Broad Research
Generate 10-15 targeted search queries across ALL of these sources:
- **Office du tourisme**: search for the city's official tourism website (e.g. "office du tourisme Cannes", "visit cannes", "cannes tourisme officiel"). These sites have the most reliable and complete listings.
- **Google**: general city info, weather, transport, what's special about the area
- **TripAdvisor**: top activities and restaurants matching the goal and budget
- **Google Maps**: specific venues, addresses, distances in the target area
- **Luma**: local events happening on the target date
- **GetYourGuide**: bookable activities with prices
- **Eventbrite / local event sites**: current events, festivals, exhibitions happening around the target date

You MUST find at least **50 options total** across all categories (activities, restaurants, shops, points of interest, events). Cast a wide net. Do multiple rounds of searches if needed.

IMPORTANT for large cities: ALWAYS scope your searches to a specific neighborhood or radius. Never search for "things to do in Paris" — search for "cours de boxe Marais samedi matin moins de 20€".

### Pass 2 — Analyze & Identify Gaps
After the broad search, check your numbers:
- Do you have 15+ activities across different categories (sport, culture, food, social, nature...)?
- Do you have 10+ restaurants/cafés/food spots in the budget?
- Do you have 5+ current events (exhibitions, festivals, markets, meetups)?
- Do you have 10+ points of interest (monuments, viewpoints, hidden spots, shops, boutiques)?
- Do you have 5+ shops/boutiques (local artisans, bookshops, vintage stores, markets)?
- Are the places geographically close enough for the quest duration?
- Do you know the weather?

If you're under 50 total options, do MORE searches. Search for different categories: bookshops, vintage stores, street art, viewpoints, local artisans, specialty food shops, sports facilities, parks, beaches, etc.

### Pass 3 — Targeted Research
Fill the gaps with precise queries:
- Exact opening hours and prices
- Walking distances between potential checkpoints
- Search the office du tourisme website for events this week/month
- Look for temporary exhibitions, pop-up shops, seasonal activities
- Backup options if something doesn't fit

### Pass 4 — Final Compilation
Compile everything into a structured CityContext. You MUST have at least 50 entries total across activities, restaurants, events, and points_of_interest. The Quest Writer needs lots of options to build a great quest.

## IMPORTANT: Don't over-search
You have a maximum of ~6 rounds of tool calls. If the search APIs return few results or are rate-limited, DO NOT keep retrying the same queries. Instead, combine whatever search results you got with your own verified knowledge of the city. You know many real places — use that knowledge! After 4-5 rounds of searches, call compile_results immediately with everything you have.

## Rules
- ONLY include REAL places that actually exist — never invent venues
- Always include addresses when possible
- Respect the budget — don't suggest €50 restaurants for a €30 budget
- Consider the datetime — don't suggest places that are closed
- Prefer diverse options — mix of activity types
- For the difficulty level:
  - easy-peasy: mainstream, accessible, well-known places
  - life-maxing: hidden gems, slightly challenging, off the beaten path
  - god-mode: extreme, niche, physically demanding, unusual experiences

## Output
After your research is complete, call the `compile_results` tool with your final structured findings.
Always write your notes and reasoning in French since the users are French-speaking.
"""

COMPILE_RESULTS_TOOL = {
    "name": "compile_results",
    "description": "Compile all research into a final structured CityContext. Call this when you've gathered enough data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "neighborhood": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "weather": {"type": "string"},
                    "temperature": {"type": "string"},
                },
                "required": ["city"],
            },
            "city_description": {
                "type": "string",
                "description": "Long factual briefing (800-1500 words, in French) about the city: history, geography, culture, landmarks, dark history, mysteries, famous people, local quirks. Dense factual reference material, NOT romanticized.",
            },
            "activities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "source": {"type": "string"},
                        "category": {"type": "string"},
                        "price": {"type": "number"},
                        "address": {"type": "string"},
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                        "rating": {"type": "number"},
                        "url": {"type": "string"},
                        "opening_hours": {"type": "string"},
                        "bookable": {"type": "boolean"},
                        "duration_minutes": {"type": "integer"},
                    },
                    "required": ["name", "description", "source", "category"],
                },
            },
            "restaurants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "cuisine": {"type": "string"},
                        "price_range": {"type": "string"},
                        "avg_price": {"type": "number"},
                        "address": {"type": "string"},
                        "rating": {"type": "number"},
                        "url": {"type": "string"},
                        "opening_hours": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            "shops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "category": {"type": "string", "description": "bookshop, vintage, artisan, market, specialty food, etc."},
                        "address": {"type": "string"},
                        "url": {"type": "string"},
                        "opening_hours": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "source": {"type": "string"},
                        "date": {"type": "string"},
                        "time": {"type": "string"},
                        "address": {"type": "string"},
                        "price": {"type": "number"},
                        "url": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            "points_of_interest": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "category": {"type": "string"},
                        "address": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            "transport": {
                "type": "object",
                "properties": {
                    "walking_friendly": {"type": "boolean"},
                    "public_transport": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
            },
            "current_news": {
                "type": "array",
                "description": "Current news items for high_stakes narrative anchoring. Only populate if tone is high_stakes.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "summary": {"type": "string"},
                        "source": {"type": "string"},
                        "date": {"type": "string"},
                        "url": {"type": "string"},
                        "relevance_for_narrative": {"type": "string", "description": "Why this news could be woven into a thriller/spy/Da Vinci Code narrative"},
                    },
                    "required": ["name", "summary"],
                },
            },
            "raw_notes": {"type": "string", "description": "Your research notes, gaps identified, and recommendations for the Quest Writer."},
        },
        "required": ["location", "city_description", "activities", "raw_notes"],
    },
}

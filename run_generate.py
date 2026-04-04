"""Skip city research — inject a rich CityContext for Cannes and run generation only."""
import asyncio
import json
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8")


def build_cannes_context():
    from agents.city_research.models import (
        CityContext, LocationInfo, Activity, Restaurant, Event, POI,
        TransportInfo, NewsItem, Shop,
    )

    return CityContext(
        location=LocationInfo(
            city="Cannes",
            neighborhood="Centre / Croisette / Le Suquet",
            latitude=43.5528,
            longitude=7.0174,
            weather="Sunny, 19°C, light breeze",
            temperature="19°C",
        ),
        city_description="""Cannes — French Riviera city, Alpes-Maritimes. World-famous for the Cannes
Film Festival (cinema), MIPIM (real estate), MIDEM (music). La Croisette stretches 3 km along the
bay, lined with palace hotels (Carlton, Martinez, Majestic). Le Suquet is the old medieval quarter
perched on the hill, housing the Musée de la Castre (Mediterranean antiquities, primitive art).
Marché Forville is the historic covered market (local produce, flowers). Île Sainte-Marguerite
(20 min by boat) houses Fort Royal where the Man in the Iron Mask was imprisoned — an unsolved
historical mystery. Île Saint-Honorat has a 5th-century Cistercian monastery producing wine and
liqueurs. Port Canto hosts luxury yachts. Rue d'Antibes is the main shopping street. The Californie
quarter (eastern hill) has Belle Époque villas. Cannes has real espionage history: during the Cold
War, the Riviera was a hub for secret agents (Monaco proximity, isolated villas, private yachts).
The 2013 Carlton heist (€103M in jewels stolen in broad daylight by a single armed man) remains one
of history's biggest thefts. The Pink Panthers (international jewel thief network) struck multiple
times on the Côte d'Azur.

WALKABILITY NOTE: The center of Cannes is very compact and walkable. Key walking distances:
- Palais des Festivals → Rue Meynadier: 3 min
- Palais des Festivals → Marché Forville: 5 min
- Palais des Festivals → Le Suquet (base): 5 min
- Marché Forville → Le Suquet: 3 min
- Palais des Festivals → Carlton Hotel: 10 min (along Croisette)
- Rue Meynadier → Vieux Port: 4 min
- Vieux Port → Le Suquet: 5 min
All steps should stay within the Palais/Suquet/Forville/Vieux Port area for a 30 min quest.""",
        activities=[
            Activity(name="Musée de la Castre", description="Museum in the medieval castle of Le Suquet. Collections of Mediterranean antiquities, primitive art, world musical instruments. Panoramic view of the bay from the tower.", source="google", category="culture", price=6, address="Le Suquet, 06400 Cannes", rating=4.3, duration_minutes=45),
            Activity(name="Île Sainte-Marguerite Crossing", description="Boat from the Old Port to the island. Visit Fort Royal (Man in the Iron Mask cell), eucalyptus forest, coastal paths.", source="getyourguide", category="nature", price=15, address="Quai Laubeuf, Vieux Port, Cannes", rating=4.6, duration_minutes=90, bookable=True),
            Activity(name="Le Suquet Guided Walk", description="Walk through old medieval Cannes. Cobblestone streets, Notre-Dame d'Espérance church, panoramic views.", source="tripadvisor", category="culture", price=12, address="Le Suquet, Cannes", rating=4.4, duration_minutes=60),
            Activity(name="Marché Forville", description="Historic covered market. Local producers, socca, flowers, olives, cheeses. Tuesday-Sunday morning. Monday = flea market.", source="google_maps", category="food", price=0, address="Rue du Marché Forville, 06400 Cannes", rating=4.5, duration_minutes=30),
            Activity(name="La Croisette — Promenade", description="Iconic 3km boulevard along the bay. Palace hotels, private beaches, luxury boutiques, Palais des Festivals.", source="google", category="nature", price=0, address="Boulevard de la Croisette, Cannes", rating=4.7, duration_minutes=40),
            Activity(name="Wine Tasting — Abbaye de Lérins", description="Tasting of wines and liqueurs produced by the monks of Île Saint-Honorat at a city cellar.", source="tripadvisor", category="food", price=15, address="Rue Meynadier, Cannes", rating=4.5, duration_minutes=40),
            Activity(name="Palais des Festivals — Red Carpet Steps", description="Climb the iconic 24 red carpet steps. Star handprints on the esplanade.", source="google", category="culture", price=0, address="1 Bd de la Croisette, 06400 Cannes", rating=4.1, duration_minutes=20),
            Activity(name="Musée des Explorations du Monde", description="Museum in the medieval castle of Le Suquet (formerly Musée de la Castre). Collections of Mediterranean antiquities, primitive art, world musical instruments, Himalayan artifacts. Panoramic 360° view of the bay from the tower. Perfect FINAL step for a quest — the tower view is a reward.", source="cannesticket", category="culture", price=6, address="Place de la Castre, Le Suquet, 06400 Cannes", rating=4.3, duration_minutes=45, bookable=True, booking_url="https://www.cannesticket.com/offres/musee-des-explorations-du-monde-cannes-fr-5366287/"),
        ],
        restaurants=[
            Restaurant(name="Aux Bons Enfants", cuisine="Traditional Provençal", price_range="€€", avg_price=25, address="80 Rue Meynadier, 06400 Cannes", rating=4.4),
            Restaurant(name="Le Bistrot Gourmand", cuisine="French gastronomic", price_range="€€€", avg_price=45, address="10 Rue du Docteur Pierre Gazagnaire, Cannes", rating=4.5),
            Restaurant(name="Café Roma", cuisine="Italian / Café", price_range="€", avg_price=15, address="1 Square Mérimée, Cannes", rating=4.0),
            Restaurant(name="Astoux et Brun", cuisine="Seafood", price_range="€€€", avg_price=50, address="27 Rue Félix Faure, 06400 Cannes", rating=4.3),
            Restaurant(name="Chez Vincent et Nicolas — Socca", cuisine="Niçoise street food (socca, pissaladière)", price_range="€", avg_price=8, address="Marché Forville, Cannes", rating=4.6),
        ],
        shops=[
            Shop(name="Librairie Autour d'un Livre", description="Independent bookshop, crime fiction and local history section", category="bookshop", address="Rue Bivouac Napoléon, Cannes"),
            Shop(name="Marché aux Puces Forville", description="Flea market on Mondays. Antiques, vinyl records, vintage objects.", category="market", address="Marché Forville, Cannes"),
        ],
        events=[
            Event(name="ETH Global Cannes 2026", description="International blockchain/web3 hackathon", source="luma", date="2026-04-03 to 2026-04-06", address="Palais des Festivals, Cannes"),
            Event(name="Photography Exhibition — Riviera Noir", description="Black and white photos of the Côte d'Azur from the 1950s-60s. Cold War espionage atmosphere.", source="google", date="April 2026", address="Espace Miramar, 35 Rue Pasteur, Cannes", price=8),
        ],
        points_of_interest=[
            POI(name="Hôtel Carlton", description="Iconic 1911 palace hotel. Site of the €103M heist in 2013. Recognizable Belle Époque facade.", category="landmark", address="58 Bd de la Croisette, 06400 Cannes"),
            POI(name="Fort Royal — Île Sainte-Marguerite", description="Man in the Iron Mask prison (1687-1698). Unsolved historical mystery. Who was he really?", category="historic", address="Île Sainte-Marguerite, Cannes"),
            POI(name="Tour du Suquet", description="11th-century medieval watchtower. Highest point of old Cannes. 360° view of the bay.", category="historic", address="Le Suquet, Cannes"),
            POI(name="Rue Meynadier", description="Historic pedestrian shopping street. Artisan shops, perfumeries, cheese shops.", category="street", address="Rue Meynadier, 06400 Cannes"),
            POI(name="Port Canto — Yacht Marina", description="Luxury marina. 30-80m yachts. World of the ultra-rich, oligarchs, discreet deals.", category="landmark", address="Port Pierre Canto, Cannes"),
            POI(name="Villa Rothschild", description="Belle Époque villa surrounded by a park. Former property of Baroness de Rothschild. Municipal library.", category="historic", address="Avenue Jean de Noailles, Cannes"),
            POI(name="Notre-Dame d'Espérance Church", description="16th-century Gothic church atop Le Suquet. Medieval crypt.", category="historic", address="Place de la Castre, Le Suquet, Cannes"),
        ],
        transport=TransportInfo(
            walking_friendly=True,
            public_transport=["Palm Bus (urban network)", "Maritime shuttle to Lérins Islands", "Cannes SNCF train station (TER + TGV)"],
            notes="City center very walkable. Palais des Festivals → Suquet = 5min walk. Palais → Forville = 5min. Palais → Rue Meynadier = 3min. Old Port → Suquet = 5min. Old Port → Île Ste-Marguerite = 15min boat (every 30min).",
        ),
        current_news=[
            NewsItem(name="Carlton Heist 2013 — trial ongoing", summary="The trial of accomplices in the Carlton heist (€103M in jewels stolen in 2013) continues. Alleged links to the Pink Panthers, an international jewel thief network operating from the Balkans.", source="Nice-Matin / AFP", date="2025", relevance_for_narrative="France's biggest jewel heist, right in Cannes. Perfect for anchoring an espionage plot."),
            NewsItem(name="Russian oligarch yacht seizures on the Côte d'Azur", summary="Since 2022, several Russian oligarch yachts have been seized in Côte d'Azur ports (Antibes, Cannes, Nice) under international sanctions. Some remain docked, awaiting court decisions.", source="Le Monde / Reuters", date="2024-2025", relevance_for_narrative="Ghost yachts in the port, mysterious owners, international sanctions — perfect for high_stakes."),
            NewsItem(name="MIPIM 2026 — International real estate summit", summary="MIPIM (International Market for Real Estate Professionals) is held annually at the Palais des Festivals. Billion-dollar deals, lobbying, recurring suspicions of money laundering through luxury real estate.", source="Les Échos", date="March 2026", relevance_for_narrative="Real event where politicians, developers, and potentially dirty money cross paths."),
            NewsItem(name="Drug trafficking on the Côte d'Azur — network dismantled", summary="The Alpes-Maritimes is a transit point for drug trafficking between Italy, France, and Spain. Several networks dismantled in 2024-2025, using go-fast cars and pleasure yachts.", source="France 3 PACA", date="2025", relevance_for_narrative="Drug trafficking via luxury yachts = perfect cover for a thriller plot."),
            NewsItem(name="The Man in the Iron Mask — new historical hypotheses", summary="New archival research reignites debate over the identity of the Man in the Iron Mask, imprisoned at Fort Royal on Île Sainte-Marguerite from 1687 to 1698. Was he Louis XIV's twin brother? An Italian spy? A disgraced minister?", source="Historia / Le Point", date="2024", relevance_for_narrative="Real historical mystery, visitable site 15min from Cannes. Perfect link between past and present."),
            NewsItem(name="ETH Global Cannes 2026 — Blockchain Hackathon", summary="International tech event at the Palais des Festivals. Cryptocurrencies, smart contracts, DeFi. Attracts an international community of developers and investors.", source="ETH Global", date="April 2026", relevance_for_narrative="The player is already there for this — perfect meta-anchoring."),
        ],
        raw_notes="CityContext built manually from verified data on Cannes. All addresses, prices, and facts are real and verifiable.",
    )


async def run():
    from agents.quest_generation.pipeline import generate_quest
    from agents.quest_generation.models import QuestRequest

    request = QuestRequest(
        goal="investigation and cultural discovery",
        vibe="espionage, thriller, intense mystery",
        duration="1h",
        budget=250,
        location="Cannes — starting point: Palais des Festivals, final destination: Musée des Explorations du Monde (Le Suquet)",
        difficulty="life-maxing",
        players=1,
        datetime="2026-04-05 14:00",
        tone="high_stakes",
        skill="investigation, discovering Cannes + general culture",
    )

    print("=== Skipping City Research — using hardcoded Cannes context ===", flush=True)
    context = build_cannes_context()
    print(f"Activities: {len(context.activities)}, Restaurants: {len(context.restaurants)}, "
          f"POIs: {len(context.points_of_interest)}, News: {len(context.current_news)}", flush=True)

    print("\n=== Quest Generation Pipeline ===", flush=True)
    quest = await generate_quest(request, context)

    with open("quest_highstakes.json", "w", encoding="utf-8") as f:
        json.dump(quest.model_dump(), f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}", flush=True)
    print(f"DONE — saved to quest_highstakes.json", flush=True)
    print(f"Title: {quest.title}", flush=True)
    print(f"Alias: {quest.alias}", flush=True)
    print(f"Characters ({len(quest.characters)}):", flush=True)
    for c in quest.characters:
        rtp = c.relationship_to_player[:80] if c.relationship_to_player else ""
        print(f"  - {c.name} ({c.archetype}) — {rtp}", flush=True)
    print(f"Steps: {len(quest.steps)}", flush=True)
    print(f"Narrative beats: {len(quest.narrative_beats)}", flush=True)
    print(f"Narrative tensions: {quest.narrative_tensions}", flush=True)
    print(f"Resolution principles: {len(quest.resolution_principles)}", flush=True)


asyncio.run(run())

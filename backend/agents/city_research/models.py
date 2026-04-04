from __future__ import annotations
from pydantic import BaseModel, Field


class QuestRequest(BaseModel):
    goal: str = Field(description="What the user wants to achieve: sport, culture, music, meeting people, etc.")
    vibe: str = Field(default="", description="Desired atmosphere: mystère, aventure, chill, epic, etc.")
    duration: str = Field(description="Quest duration: 5mn, 2h, 4h, etc.")
    budget: float = Field(description="Budget in euros")
    location: str = Field(description="City or neighborhood: Cannes, Paris 3ème, etc.")
    difficulty: str = Field(default="life-maxing", description="easy-peasy | life-maxing | god-mode")
    players: int = Field(default=1, description="Number of players")
    datetime: str = Field(description="When the quest starts: 2026-04-05 10:00")


class Activity(BaseModel):
    name: str
    description: str
    source: str = Field(description="tripadvisor, getyourguide, google, luma, etc.")
    category: str = Field(description="sport, culture, food, nightlife, nature, etc.")
    price: float | None = Field(default=None, description="Price in euros, None if free")
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    url: str = ""
    opening_hours: str = ""
    bookable: bool = False
    booking_url: str = ""
    duration_minutes: int | None = None


class Restaurant(BaseModel):
    name: str
    cuisine: str = ""
    price_range: str = Field(default="", description="€, €€, €€€")
    avg_price: float | None = None
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    url: str = ""
    opening_hours: str = ""


class Event(BaseModel):
    name: str
    description: str = ""
    source: str = Field(default="luma", description="luma, google, etc.")
    date: str = ""
    time: str = ""
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    price: float | None = None
    url: str = ""


class POI(BaseModel):
    name: str
    description: str = ""
    category: str = ""
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None


class LocationInfo(BaseModel):
    city: str
    neighborhood: str = ""
    latitude: float | None = None
    longitude: float | None = None
    weather: str = ""
    temperature: str = ""


class TransportInfo(BaseModel):
    walking_friendly: bool = True
    public_transport: list[str] = Field(default_factory=list)
    notes: str = ""


class Shop(BaseModel):
    name: str
    description: str = ""
    category: str = Field(default="", description="bookshop, vintage, artisan, market, etc.")
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    url: str = ""
    opening_hours: str = ""


class NewsItem(BaseModel):
    name: str
    summary: str = ""
    source: str = ""
    date: str = ""
    url: str = ""
    relevance_for_narrative: str = Field(default="", description="Why this news item could be woven into a high_stakes narrative")


class CityContext(BaseModel):
    location: LocationInfo
    city_description: str = Field(default="", description="Long factual briefing about the city for the Quest Writer LLM.")
    activities: list[Activity] = Field(default_factory=list)
    restaurants: list[Restaurant] = Field(default_factory=list)
    shops: list[Shop] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    points_of_interest: list[POI] = Field(default_factory=list)
    transport: TransportInfo = Field(default_factory=TransportInfo)
    current_news: list[NewsItem] = Field(default_factory=list, description="Current news/events for high_stakes narrative anchoring")
    raw_notes: str = Field(default="", description="Free-form notes from the research agent")

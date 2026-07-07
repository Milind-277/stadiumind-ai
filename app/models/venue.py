"""app/models/venue.py — Venue, Zone, and Gate domain models."""
from dataclasses import dataclass
from typing import List


@dataclass
class Gate:
    id: str
    name: str
    location: str      # e.g. "North", "South", "East", "West"
    accessible: bool
    open_time: str     # "HH:MM"


@dataclass
class Zone:
    id: str
    name: str
    type: str          # "seating" | "concourse" | "food" | "medical" | "exit"
    capacity: int
    level: int         # Floor level (0 = ground)
    accessible: bool


@dataclass
class FoodCourt:
    id: str
    name: str
    zone_id: str
    cuisine_types: List[str]
    halal_available: bool
    vegetarian_available: bool
    wait_time_minutes: int


@dataclass
class Venue:
    id: str
    name: str
    city: str
    country: str
    capacity: int
    address: str
    latitude: float
    longitude: float
    gates: List[Gate]
    zones: List[Zone]
    food_courts: List[FoodCourt]
    accessibility_services: List[str]
    parking_zones: List[str]
    nearest_transit: str

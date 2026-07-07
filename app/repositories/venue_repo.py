"""app/repositories/venue_repo.py — JSON-backed Venue repository."""
from typing import Any, Dict

from app.models.venue import Venue, Zone, Gate, FoodCourt
from .json_base import JSONRepository


class VenueRepository(JSONRepository):
    def _get_filename(self) -> str:
        return "venues.json"

    def _to_model(self, raw: Dict[str, Any]) -> Venue:
        gates = [
            Gate(
                id=g["id"], name=g["name"], location=g["location"],
                accessible=g["accessible"], open_time=g["open_time"],
            )
            for g in raw.get("gates", [])
        ]
        zones = [
            Zone(
                id=z["id"], name=z["name"], type=z["type"],
                capacity=z["capacity"], level=z["level"],
                accessible=z["accessible"],
            )
            for z in raw.get("zones", [])
        ]
        food_courts = [
            FoodCourt(
                id=f["id"], name=f["name"], zone_id=f["zone_id"],
                cuisine_types=f["cuisine_types"],
                halal_available=f["halal_available"],
                vegetarian_available=f["vegetarian_available"],
                wait_time_minutes=f["wait_time_minutes"],
            )
            for f in raw.get("food_courts", [])
        ]
        return Venue(
            id=raw["id"],
            name=raw["name"],
            city=raw["city"],
            country=raw["country"],
            capacity=raw["capacity"],
            address=raw["address"],
            latitude=raw["latitude"],
            longitude=raw["longitude"],
            gates=gates,
            zones=zones,
            food_courts=food_courts,
            accessibility_services=raw.get("accessibility_services", []),
            parking_zones=raw.get("parking_zones", []),
            nearest_transit=raw.get("nearest_transit", ""),
        )

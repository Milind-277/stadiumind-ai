"""app/repositories/match_repo.py — JSON-backed Match repository."""

from typing import Any, Dict

from app.models.match import Match, Team

from .json_base import JSONRepository


def _build_team(raw: Dict) -> Team:
    return Team(
        id=raw["id"],
        name=raw["name"],
        code=raw["code"],
        flag_emoji=raw["flag_emoji"],
        group=raw.get("group", ""),
    )


class MatchRepository(JSONRepository):
    def _get_filename(self) -> str:
        return "matches.json"

    def _to_model(self, raw: Dict[str, Any]) -> Match:
        return Match(
            id=raw["id"],
            home_team=_build_team(raw["home_team"]),
            away_team=_build_team(raw["away_team"]),
            venue_id=raw["venue_id"],
            venue_name=raw["venue_name"],
            kickoff_utc=raw["kickoff_utc"],
            stage=raw["stage"],
            group=raw.get("group"),
            status=raw["status"],
            home_score=raw.get("home_score"),
            away_score=raw.get("away_score"),
            attendance=raw.get("attendance"),
            highlights=raw.get("highlights"),
        )

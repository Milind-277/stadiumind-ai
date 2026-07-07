"""app/models/match.py — Match and Team domain models."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Team:
    id: str
    name: str
    code: str          # 3-letter FIFA code e.g. "BRA"
    flag_emoji: str
    group: str


@dataclass
class Match:
    id: str
    home_team: Team
    away_team: Team
    venue_id: str
    venue_name: str
    kickoff_utc: str   # ISO 8601
    stage: str         # "Group Stage", "Quarter-Final", etc.
    group: Optional[str]
    status: str        # "scheduled" | "live" | "completed"
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    attendance: Optional[int] = None
    highlights: Optional[str] = None

    @property
    def score_display(self) -> str:
        if self.home_score is None:
            return "vs"
        return f"{self.home_score} – {self.away_score}"

    @property
    def is_live(self) -> bool:
        return self.status == "live"

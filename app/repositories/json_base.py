"""
app/repositories/json_base.py — Base class for all JSON-backed repositories.

Handles atomic file reads and writes. All JSON repos extend this class.
Atomic write: write to temp file → rename (prevents partial reads on crash).
"""
import json
import os
import tempfile
import uuid
from typing import Any, Callable, Dict, List, Optional

from .base import BaseRepository


class JSONRepository(BaseRepository):
    """
    Concrete JSON-file-backed repository.
    Subclasses must set `self.file_path` and implement `_to_model()`.
    """

    file_path: str = ""        # Set by subclass (e.g. "data/matches.json")
    id_field: str = "id"       # Primary key field name in JSON

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = data_dir
        self.file_path = os.path.join(data_dir, self._get_filename())

    def _get_filename(self) -> str:
        """Override in subclass to return the JSON file name."""
        raise NotImplementedError

    def _to_model(self, raw: Dict[str, Any]) -> Any:
        """Override in subclass to convert raw dict → domain model."""
        return raw

    def _to_dict(self, record: Any) -> Dict[str, Any]:
        """Convert a domain model → raw dict for persistence.
        Default: works if record is already a dict or has __dict__."""
        if isinstance(record, dict):
            return record
        if hasattr(record, "__dataclass_fields__"):
            import dataclasses
            return dataclasses.asdict(record)
        return vars(record)

    # ── Internal Helpers ───────────────────────────────────────────────────────

    def _read_all_raw(self) -> List[Dict[str, Any]]:
        """Read and parse the JSON file. Returns empty list if file missing."""
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write_all_raw(self, records: List[Dict[str, Any]]) -> None:
        """Atomically write records to the JSON file."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        dir_name = os.path.dirname(self.file_path)
        with tempfile.NamedTemporaryFile(
            "w",
            dir=dir_name if dir_name else ".",
            delete=False,
            encoding="utf-8",
            suffix=".tmp",
        ) as tmp:
            json.dump(records, tmp, indent=2, ensure_ascii=False, default=str)
            tmp_path = tmp.name
        os.replace(tmp_path, self.file_path)

    # ── BaseRepository Implementation ─────────────────────────────────────────

    def find_all(self) -> List[Any]:
        return [self._to_model(r) for r in self._read_all_raw()]

    def find_by_id(self, record_id: str) -> Optional[Any]:
        for raw in self._read_all_raw():
            if raw.get(self.id_field) == record_id:
                return self._to_model(raw)
        return None

    def find_where(self, predicate: Callable[[Any], bool]) -> List[Any]:
        return [m for m in self.find_all() if predicate(m)]

    def save(self, record: Any) -> Any:
        records = self._read_all_raw()
        raw = self._to_dict(record)
        if not raw.get(self.id_field):
            raw[self.id_field] = str(uuid.uuid4())[:8]
        records.append(raw)
        self._write_all_raw(records)
        return self._to_model(raw)

    def update(self, record_id: str, data: Dict[str, Any]) -> Optional[Any]:
        records = self._read_all_raw()
        updated = None
        for i, raw in enumerate(records):
            if raw.get(self.id_field) == record_id:
                records[i] = {**raw, **data}
                updated = self._to_model(records[i])
                break
        if updated is not None:
            self._write_all_raw(records)
        return updated

    def delete(self, record_id: str) -> bool:
        records = self._read_all_raw()
        new_records = [r for r in records if r.get(self.id_field) != record_id]
        if len(new_records) == len(records):
            return False
        self._write_all_raw(new_records)
        return True

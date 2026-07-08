"""
app/repositories/base.py — Abstract Repository Interface.

All data access goes through this contract. Swap the concrete implementation
(JSON → PostgreSQL → Firestore) without touching any service code.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar("T")


class BaseRepository(ABC):
    """Abstract CRUD interface that all concrete repositories must implement."""

    @abstractmethod
    def find_all(self) -> List[Any]:
        """Return all records."""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, record_id: str) -> Optional[Any]:
        """Return a single record by ID, or None if not found."""
        raise NotImplementedError

    @abstractmethod
    def find_where(self, predicate: Callable[[Any], bool]) -> List[Any]:
        """Return all records matching the predicate function."""
        raise NotImplementedError

    @abstractmethod
    def save(self, record: Any) -> Any:
        """Persist a new record and return it."""
        raise NotImplementedError

    @abstractmethod
    def update(self, record_id: str, data: Dict[str, Any]) -> Optional[Any]:
        """Update an existing record's fields and return the updated record."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        """Delete a record by ID. Return True if deleted, False if not found."""
        raise NotImplementedError

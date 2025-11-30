import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class User:
    id: Optional[uuid.UUID]
    username: str
    password_hash: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "User":
        return cls(
            id=row.get("id"),
            username=row["username"],
            password_hash=row.get("password_hash"),
            roles=list(row.get("roles") or []),
            updated_at=row.get("updated_at"),
            deleted_at=row.get("deleted_at"),
        )

    def to_ui_row(self) -> Dict[str, Any]:
        return {
            "id": str(self.id) if self.id else "",
            "username": self.username,
            "password_hash": self.password_hash,
            "roles": ", ".join(self.roles) if self.roles else "",
            "updated_at": (
                self.updated_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                if self.updated_at else ""
            ),
            "deleted_at": (
                self.deleted_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                if self.deleted_at else ""
            ),
        }

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# -------------------------
# User model
# -------------------------
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
                if self.updated_at
                else ""
            ),
            "deleted_at": (
                self.deleted_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                if self.deleted_at
                else ""
            ),
        }


# -------------------------
# Edge model (from slide)
# -------------------------
@dataclass
class Edge:
    id: Optional[uuid.UUID]
    serial_number: str
    type: str
    updated_at: Optional[datetime] = None
    # Ownership (via link table). We keep username only for display convenience.
    owner_user_id: Optional[uuid.UUID] = None
    owner_username: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Edge":
        return cls(
            id=row.get("id"),
            serial_number=row.get("serial_number"),
            type=row.get("type"),
            updated_at=row.get("updated_at"),
            owner_user_id=row.get("owner_user_id"),
            owner_username=row.get("owner_username"),
        )

    def to_ui_row(self) -> Dict[str, Any]:
        return {
            "id": str(self.id) if self.id else "",
            "serial_number": self.serial_number,
            "type": self.type or "",
            "updated_at": (
                self.updated_at.astimezone(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
                if self.updated_at
                else ""
            ),
            "owner": self.owner_username or "",
        }

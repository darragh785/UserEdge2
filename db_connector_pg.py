import sys
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict

import bcrypt
import psycopg
from psycopg.rows import dict_row

from domain_models import User, Edge
import os


class PostgresConnector:
    def __init__(self):
        # Build connection string from environment variables
        parts = [
            f"host={os.getenv('DB_HOST', '127.0.0.1')}",
            f"port={os.getenv('DB_PORT', '5432')}",
            f"dbname={os.getenv('DB_NAME', 'projectdb')}",
            f"user={os.getenv('DB_USER', 'postuser')}",
            f"password={os.getenv('DB_PASSWORD', '')}",
        ]

        if os.getenv('DB_SSLMODE'):
            parts.append(f"sslmode={os.getenv('DB_SSLMODE', 'prefer')}")

        self.__connectString = " ".join(parts)

        # ========== DEBUG PRINTS ==========
        print("===== DEBUG: PostgreSQL Connection Info =====")
        print("DB_HOST      =", os.getenv("DB_HOST"))
        print("DB_PORT      =", os.getenv("DB_PORT"))
        print("DB_NAME      =", os.getenv("DB_NAME"))
        print("DB_USER      =", os.getenv("DB_USER"))
        print("DB_PASSWORD  =", os.getenv("DB_PASSWORD"))
        print("DB_SSLMODE   =", os.getenv("DB_SSLMODE"))
        print("FULL CONNECTION STRING:")
        print(self.__connectString)
        print("====================================================")

    # ------------------------------------------------------------------
    def get_conn(self):
        return psycopg.connect(self.__connectString, row_factory=dict_row)

    # ====================== USERS =====================================
    def get_all_users(self) -> List[User]:
        """Returns list of all users"""
        q = """
            SELECT *
            FROM public.users
            ORDER BY username
        """
        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q)
            return [User.from_row(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    def create_user(self, username: str, password: str, roles: List[str]) -> uuid.UUID:
        now = datetime.now(timezone.utc)
        pw_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        q = """
            INSERT INTO public.users 
                (username, password_hash, roles, updated_at, deleted_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """

        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q, (username.strip(), pw_hash, roles, now, None))
            return cur.fetchone()["id"]

    # ------------------------------------------------------------------
    def update_user(
        self,
        user_id: str | uuid.UUID,
        username: str,
        roles: List[str],
        new_password: Optional[str],
    ) -> None:

        if new_password:
            pw_hash = bcrypt.hashpw(
                new_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            q = """
                UPDATE public.users
                SET username=%s, roles=%s, password_hash=%s
                WHERE id=%s
            """
            params = (username.strip(), roles, pw_hash, user_id)
        else:
            q = """
                UPDATE public.users
                SET username=%s, roles=%s
                WHERE id=%s
            """
            params = (username.strip(), roles, user_id)

        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q, params)

    # ------------------------------------------------------------------
    def soft_delete_user(self, user_id: str | uuid.UUID, delete: bool) -> None:
        deleted_at = datetime.now(timezone.utc) if delete else None

        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE public.users SET deleted_at=%s WHERE id=%s",
                (deleted_at, user_id),
            )

    # ------------------------------------------------------------------
    def hard_delete_user(self, user_id: str | uuid.UUID) -> None:
        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM public.users WHERE id=%s", (user_id,))

    # ====================== EDGES =====================================
    #region -------edge CRUD methods against edges table -------------------------
    def get_all_edges(self, *, owner_id: Optional[str | uuid.UUID] = None) -> List[Edge]:
        """
        Return edges with optional owner filter.

        - If owner_id is provided: only edges linked to that user.
        - Otherwise: all edges, with (at most one) owner shown if present.
        - We do NOT filter out soft-deleted users so admins can see devices of deleted users.
        """
        if owner_id:
            q = """
                SELECT e.*,
                       u.id       AS owner_user_id,
                       u.username AS owner_username
                FROM public.edges e
                JOIN public.user_edge_link l
                    ON l.edge_id = e.id AND l.user_id = %s
                LEFT JOIN public.users u
                    ON u.id = l.user_id
                ORDER BY e.serial_number
            """
            params = (owner_id,)
        else:
            # Choose (at most) one owner per edge for display using a lateral join
            q = """
                SELECT e.*,
                       u.id       AS owner_user_id,
                       u.username AS owner_username
                FROM public.edges e
                LEFT JOIN LATERAL (
                    SELECT l.user_id
                    FROM public.user_edge_link l
                    WHERE l.edge_id = e.id
                    LIMIT 1
                ) l ON TRUE
                LEFT JOIN public.users u
                    ON u.id = l.user_id
                ORDER BY e.serial_number
            """
            params: tuple = ()

        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q, params)
            rows = cur.fetchall()
            return [Edge.from_row(r) for r in rows]

    def create_edge(self, serial_number: str, type_: str) -> uuid.UUID:
        q = """
            INSERT INTO public.edges (serial_number, type)
            VALUES (%s, %s)
            RETURNING id
        """
        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q, (serial_number.strip(), type_.strip()))
            rid = cur.fetchone()["id"]
            return rid

    def update_edge(
        self,
        edge_id: str | uuid.UUID,
        serial_number: str,
        type_: str,
    ) -> None:
        q = """
            UPDATE public.edges
            SET serial_number = %s,
                type          = %s
            WHERE id = %s
        """
        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q, (serial_number.strip(), type_.strip(), edge_id))

    def hard_delete_edge(self, edge_id: str | uuid.UUID) -> None:
        """Will cascade delete links (FK ON DELETE CASCADE)."""
        q = "DELETE FROM public.edges WHERE id = %s"
        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q, (edge_id,))
    #endregion

    # =================== USER–EDGE LINK =================================
    #region --------- EDGES: ownership (single owner enforced logically) ---------------
    def get_edge_owner_id(self, edge_id: str | uuid.UUID) -> Optional[uuid.UUID]:
        q = "SELECT user_id FROM public.user_edge_link WHERE edge_id = %s LIMIT 1"
        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q, (edge_id,))
            r = cur.fetchone()
            return r["user_id"] if r else None

    def set_edge_owner_id(
        self,
        edge_id: str | uuid.UUID,
        owner_user_id: Optional[str | uuid.UUID],
    ) -> None:
        """Replace any existing link(s) with the new single owner, or clear ownership if None."""
        with self.get_conn() as conn, conn.cursor() as cur:
            # Remove any existing links for this edge
            cur.execute("DELETE FROM public.user_edge_link WHERE edge_id = %s", (edge_id,))
            # Insert new link if provided
            if owner_user_id:
                cur.execute(
                    "INSERT INTO public.user_edge_link (user_id, edge_id) VALUES (%s, %s)",
                    (owner_user_id, edge_id),
                )

    def get_user_device_counts(self) -> Dict[str, int]:
        """Return {user_id(str): device_count(int)} for all users (includes soft-deleted)."""
        q = """
            SELECT u.id::text        AS user_id,
                   COUNT(l.edge_id)::int AS device_count
            FROM public.users u
            LEFT JOIN public.user_edge_link l
                ON l.user_id = u.id
            GROUP BY u.id
        """
        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute(q)
            rows = cur.fetchall()
            return {r["user_id"]: r["device_count"] for r in rows}
    #endregion

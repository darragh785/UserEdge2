import sys
import uuid
from datetime import datetime, timezone
from typing import List, Optional
import bcrypt
import psycopg
from psycopg.rows import dict_row
from domain_models import User
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
        print("===== DEBUG: Azure PostgreSQL Connection Info =====")
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

    # ------------------------------------------------------------------

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
        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

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

    def update_user(self, user_id: str | uuid.UUID, username: str,
                    roles: List[str], new_password: Optional[str]) -> None:

        if new_password:
            pw_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
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
                (deleted_at, user_id)
            )

    # ------------------------------------------------------------------

    def hard_delete_user(self, user_id: str | uuid.UUID) -> None:
        with self.get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM public.users WHERE id=%s", (user_id,))

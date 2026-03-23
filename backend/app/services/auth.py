from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import Settings


@dataclass
class AuthUser:
    id: int
    username: str
    role: str
    is_active: bool


class AuthStore:
    def __init__(self, *, db_path: str, session_ttl_hours: int = 24) -> None:
        self.db_path = str(Path(db_path).resolve())
        self.session_ttl_hours = max(1, min(int(session_ttl_hours or 24), 24 * 30))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_token_hash TEXT NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    user_agent TEXT,
                    ip_addr TEXT,
                    FOREIGN KEY(user_id) REFERENCES auth_users(id) ON DELETE CASCADE
                )
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_active
                ON auth_sessions(user_id, revoked_at, expires_at)
                """)
            conn.commit()

    @staticmethod
    def _normalize_role(raw: object) -> str:
        text = str(raw or "").strip().lower()
        return "admin" if text == "admin" else "trader"

    @staticmethod
    def _normalize_username(raw: object) -> str:
        return str(raw or "").strip().lower()

    @staticmethod
    def _hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
        if salt_hex:
            salt = bytes.fromhex(str(salt_hex))
        else:
            salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, 210_000)
        return salt.hex(), digest.hex()

    @staticmethod
    def _session_token_hash(token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    def ensure_user(self, *, username: str, password: str, role: str) -> None:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return
        clean_role = self._normalize_role(role)
        salt_hex, hash_hex = self._hash_password(password)
        now = self._now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM auth_users WHERE username = ?", (clean_username,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO auth_users (
                        username,
                        role,
                        password_salt,
                        password_hash,
                        is_active,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (clean_username, clean_role, salt_hex, hash_hex, now, now),
                )
            else:
                conn.execute(
                    """
                    UPDATE auth_users
                    SET role = ?, password_salt = ?, password_hash = ?, is_active = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean_role, salt_hex, hash_hex, now, int(existing["id"])),
                )
            conn.commit()

    def bootstrap_users(
        self,
        *,
        admin_username: str,
        admin_password: str,
        trader_username: str,
        trader_password: str,
        seed_enabled: bool = True,
    ) -> None:
        if not seed_enabled:
            return
        if str(admin_username or "").strip() and str(admin_password or "").strip():
            self.ensure_user(username=admin_username, password=admin_password, role="admin")
        if str(trader_username or "").strip() and str(trader_password or "").strip():
            self.ensure_user(username=trader_username, password=trader_password, role="trader")

    def authenticate(self, *, username: str, password: str) -> AuthUser | None:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, username, role, is_active, password_salt, password_hash
                FROM auth_users
                WHERE username = ?
                LIMIT 1
                """,
                (clean_username,),
            ).fetchone()
        if row is None or int(row["is_active"] or 0) != 1:
            return None
        _, computed_hash = self._hash_password(password, salt_hex=str(row["password_salt"] or ""))
        if not hmac.compare_digest(str(row["password_hash"] or ""), computed_hash):
            return None
        return AuthUser(
            id=int(row["id"]),
            username=str(row["username"] or ""),
            role=self._normalize_role(row["role"]),
            is_active=True,
        )

    def create_session(
        self,
        *,
        user: AuthUser,
        user_agent: str | None = None,
        ip_addr: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        token = secrets.token_urlsafe(48)
        token_hash = self._session_token_hash(token)
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        expires_at = (now + timedelta(hours=self.session_ttl_hours)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auth_sessions (
                    session_token_hash,
                    user_id,
                    created_at,
                    last_seen_at,
                    expires_at,
                    revoked_at,
                    user_agent,
                    ip_addr
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    token_hash,
                    int(user.id),
                    now_iso,
                    now_iso,
                    expires_at,
                    str(user_agent or "")[:255] or None,
                    str(ip_addr or "")[:120] or None,
                ),
            )
            conn.commit()
        return token, {
            "user": {"id": int(user.id), "username": user.username, "role": user.role},
            "expires_at": expires_at,
        }

    def resolve_session(self, *, session_token: str | None) -> dict[str, Any] | None:
        token = str(session_token or "").strip()
        if not token:
            return None
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        token_hash = self._session_token_hash(token)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    s.id AS session_id,
                    s.expires_at,
                    u.id AS user_id,
                    u.username,
                    u.role,
                    u.is_active
                FROM auth_sessions s
                JOIN auth_users u ON u.id = s.user_id
                WHERE s.session_token_hash = ?
                  AND s.revoked_at IS NULL
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            try:
                expires_dt = datetime.fromisoformat(
                    str(row["expires_at"] or "").replace("Z", "+00:00")
                )
            except ValueError:
                return None
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=UTC)
            if expires_dt <= now:
                conn.execute(
                    "UPDATE auth_sessions SET revoked_at = ? WHERE id = ?",
                    (now_iso, int(row["session_id"])),
                )
                conn.commit()
                return None
            if int(row["is_active"] or 0) != 1:
                return None
            next_expiry = (now + timedelta(hours=self.session_ttl_hours)).isoformat()
            conn.execute(
                "UPDATE auth_sessions SET last_seen_at = ?, expires_at = ? WHERE id = ?",
                (now_iso, next_expiry, int(row["session_id"])),
            )
            conn.commit()
        return {
            "session_id": int(row["session_id"]),
            "user": {
                "id": int(row["user_id"]),
                "username": str(row["username"] or ""),
                "role": self._normalize_role(row["role"]),
            },
            "expires_at": next_expiry,
        }

    def revoke_session(self, *, session_token: str | None) -> None:
        token = str(session_token or "").strip()
        if not token:
            return
        with self._connect() as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE session_token_hash = ? AND revoked_at IS NULL",
                (self._now_iso(), self._session_token_hash(token)),
            )
            conn.commit()

    def reset_for_tests(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM auth_sessions")
            conn.execute("DELETE FROM auth_users")
            conn.commit()


_auth_store_cache: dict[str, AuthStore] = {}


def get_auth_store(settings: Settings) -> AuthStore:
    cache_key = str(Path(settings.auth_db_path).resolve())
    store = _auth_store_cache.get(cache_key)
    if store is None:
        store = AuthStore(
            db_path=settings.auth_db_path, session_ttl_hours=settings.auth_session_ttl_hours
        )
        _auth_store_cache[cache_key] = store
    return store

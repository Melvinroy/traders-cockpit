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

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.entities import AuthLoginAttemptEntity, AuthSessionEntity, AuthUserEntity

FAILED_LOGIN_WINDOW_MINUTES = 15
FAILED_LOGIN_LIMIT = 5


@dataclass
class AuthUser:
    id: int
    username: str
    role: str
    is_active: bool


class AuthStoreBase:
    def __init__(self, *, session_ttl_hours: int = 24) -> None:
        self.session_ttl_hours = max(1, min(int(session_ttl_hours or 24), 24 * 30))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _now_iso() -> str:
        return AuthStoreBase._now().isoformat()

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

    def _login_subjects(self, *, username: str, ip_addr: str | None) -> list[str]:
        subjects: list[str] = []
        clean_username = self._normalize_username(username)
        clean_ip = str(ip_addr or "").strip()
        if clean_username:
            subjects.append(f"user:{clean_username}")
        if clean_ip:
            subjects.append(f"ip:{clean_ip}")
        return subjects

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

    def dispose(self) -> None:
        return


class FileAuthStore(AuthStoreBase):
    def __init__(self, *, db_path: str, session_ttl_hours: int = 24) -> None:
        super().__init__(session_ttl_hours=session_ttl_hours)
        self.db_path = str(Path(db_path).resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_key TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                )
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_auth_login_attempts_subject_time
                ON auth_login_attempts(subject_key, occurred_at)
                """)
            conn.commit()

    def _recent_attempt_rows(
        self,
        *,
        conn: sqlite3.Connection,
        subject_key: str,
        window_started_at: str,
    ) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT occurred_at
            FROM auth_login_attempts
            WHERE subject_key = ?
              AND occurred_at >= ?
            ORDER BY occurred_at ASC
            """,
            (subject_key, window_started_at),
        ).fetchall()

    def _cleanup_expired_login_attempts(
        self,
        *,
        conn: sqlite3.Connection,
        window_started_at: str,
    ) -> None:
        conn.execute(
            "DELETE FROM auth_login_attempts WHERE occurred_at < ?",
            (window_started_at,),
        )

    def check_login_allowed(self, *, username: str, ip_addr: str | None) -> tuple[bool, int | None]:
        now = self._now()
        window_started_at = (now - timedelta(minutes=FAILED_LOGIN_WINDOW_MINUTES)).isoformat()
        retry_after_seconds: int | None = None
        with self._connect() as conn:
            self._cleanup_expired_login_attempts(
                conn=conn,
                window_started_at=window_started_at,
            )
            conn.commit()
            for subject_key in self._login_subjects(username=username, ip_addr=ip_addr):
                rows = self._recent_attempt_rows(
                    conn=conn,
                    subject_key=subject_key,
                    window_started_at=window_started_at,
                )
                if len(rows) <= FAILED_LOGIN_LIMIT:
                    continue
                oldest = datetime.fromisoformat(str(rows[0]["occurred_at"]).replace("Z", "+00:00"))
                if oldest.tzinfo is None:
                    oldest = oldest.replace(tzinfo=UTC)
                expires_at = oldest + timedelta(minutes=FAILED_LOGIN_WINDOW_MINUTES)
                retry_after_seconds = max(1, int((expires_at - now).total_seconds()))
                break
        return retry_after_seconds is None, retry_after_seconds

    def record_login_failure(
        self,
        *,
        username: str,
        ip_addr: str | None,
    ) -> tuple[bool, int | None]:
        now_iso = self._now_iso()
        subjects = self._login_subjects(username=username, ip_addr=ip_addr)
        if not subjects:
            return True, None
        with self._connect() as conn:
            for subject_key in subjects:
                conn.execute(
                    """
                    INSERT INTO auth_login_attempts (subject_key, occurred_at)
                    VALUES (?, ?)
                    """,
                    (subject_key, now_iso),
                )
            conn.commit()
        return self.check_login_allowed(username=username, ip_addr=ip_addr)

    def clear_login_failures(self, *, username: str, ip_addr: str | None) -> None:
        subjects = self._login_subjects(username=username, ip_addr=ip_addr)
        if not subjects:
            return
        placeholders = ",".join("?" for _ in subjects)
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM auth_login_attempts WHERE subject_key IN ({placeholders})",
                tuple(subjects),
            )
            conn.commit()

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
                """
                UPDATE auth_sessions
                SET revoked_at = ?
                WHERE session_token_hash = ?
                  AND revoked_at IS NULL
                """,
                (self._now_iso(), self._session_token_hash(token)),
            )
            conn.commit()

    def reset_for_tests(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM auth_login_attempts")
            conn.execute("DELETE FROM auth_sessions")
            conn.execute("DELETE FROM auth_users")
            conn.commit()


class DatabaseAuthStore(AuthStoreBase):
    def __init__(self, *, database_url: str, session_ttl_hours: int = 24) -> None:
        super().__init__(session_ttl_hours=session_ttl_hours)
        self.database_url = database_url
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )

    def dispose(self) -> None:
        self.engine.dispose()

    def check_login_allowed(self, *, username: str, ip_addr: str | None) -> tuple[bool, int | None]:
        now = self._now()
        window_started_at = now - timedelta(minutes=FAILED_LOGIN_WINDOW_MINUTES)
        retry_after_seconds: int | None = None
        with self.SessionLocal() as db:
            db.execute(
                delete(AuthLoginAttemptEntity).where(
                    AuthLoginAttemptEntity.occurred_at < window_started_at
                )
            )
            db.commit()
            for subject_key in self._login_subjects(username=username, ip_addr=ip_addr):
                attempts = db.scalars(
                    select(AuthLoginAttemptEntity.occurred_at)
                    .where(
                        AuthLoginAttemptEntity.subject_key == subject_key,
                        AuthLoginAttemptEntity.occurred_at >= window_started_at,
                    )
                    .order_by(AuthLoginAttemptEntity.occurred_at.asc())
                ).all()
                if len(attempts) <= FAILED_LOGIN_LIMIT:
                    continue
                oldest = attempts[0]
                if oldest.tzinfo is None:
                    oldest = oldest.replace(tzinfo=UTC)
                expires_at = oldest + timedelta(minutes=FAILED_LOGIN_WINDOW_MINUTES)
                retry_after_seconds = max(1, int((expires_at - now).total_seconds()))
                break
        return retry_after_seconds is None, retry_after_seconds

    def record_login_failure(
        self,
        *,
        username: str,
        ip_addr: str | None,
    ) -> tuple[bool, int | None]:
        subjects = self._login_subjects(username=username, ip_addr=ip_addr)
        if not subjects:
            return True, None
        now = self._now()
        with self.SessionLocal() as db:
            for subject_key in subjects:
                db.add(AuthLoginAttemptEntity(subject_key=subject_key, occurred_at=now))
            db.commit()
        return self.check_login_allowed(username=username, ip_addr=ip_addr)

    def clear_login_failures(self, *, username: str, ip_addr: str | None) -> None:
        subjects = self._login_subjects(username=username, ip_addr=ip_addr)
        if not subjects:
            return
        with self.SessionLocal() as db:
            db.execute(
                delete(AuthLoginAttemptEntity).where(
                    AuthLoginAttemptEntity.subject_key.in_(subjects)
                )
            )
            db.commit()

    def ensure_user(self, *, username: str, password: str, role: str) -> None:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return
        clean_role = self._normalize_role(role)
        salt_hex, hash_hex = self._hash_password(password)
        now = self._now()
        with self.SessionLocal() as db:
            existing = db.scalar(
                select(AuthUserEntity).where(AuthUserEntity.username == clean_username).limit(1)
            )
            if existing is None:
                db.add(
                    AuthUserEntity(
                        username=clean_username,
                        role=clean_role,
                        password_salt=salt_hex,
                        password_hash=hash_hex,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                existing.role = clean_role
                existing.password_salt = salt_hex
                existing.password_hash = hash_hex
                existing.is_active = True
                existing.updated_at = now
            db.commit()

    def authenticate(self, *, username: str, password: str) -> AuthUser | None:
        clean_username = self._normalize_username(username)
        if not clean_username:
            return None
        with self.SessionLocal() as db:
            row = db.scalar(
                select(AuthUserEntity).where(AuthUserEntity.username == clean_username).limit(1)
            )
            if row is None or not row.is_active:
                return None
            _, computed_hash = self._hash_password(password, salt_hex=row.password_salt)
            if not hmac.compare_digest(row.password_hash, computed_hash):
                return None
            return AuthUser(
                id=int(row.id),
                username=row.username,
                role=self._normalize_role(row.role),
                is_active=bool(row.is_active),
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
        now = self._now()
        expires_at = now + timedelta(hours=self.session_ttl_hours)
        with self.SessionLocal() as db:
            db.add(
                AuthSessionEntity(
                    session_token_hash=token_hash,
                    user_id=int(user.id),
                    created_at=now,
                    last_seen_at=now,
                    expires_at=expires_at,
                    user_agent=str(user_agent or "")[:255] or None,
                    ip_addr=str(ip_addr or "")[:120] or None,
                )
            )
            db.commit()
        return token, {
            "user": {"id": int(user.id), "username": user.username, "role": user.role},
            "expires_at": expires_at.isoformat(),
        }

    def resolve_session(self, *, session_token: str | None) -> dict[str, Any] | None:
        token = str(session_token or "").strip()
        if not token:
            return None
        now = self._now()
        token_hash = self._session_token_hash(token)
        with self.SessionLocal() as db:
            row = db.execute(
                select(AuthSessionEntity, AuthUserEntity)
                .join(AuthUserEntity, AuthUserEntity.id == AuthSessionEntity.user_id)
                .where(
                    AuthSessionEntity.session_token_hash == token_hash,
                    AuthSessionEntity.revoked_at.is_(None),
                )
                .limit(1)
            ).first()
            if row is None:
                return None
            session_entity, user_entity = row
            expires_at = session_entity.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= now:
                session_entity.revoked_at = now
                db.commit()
                return None
            if not user_entity.is_active:
                return None
            next_expiry = now + timedelta(hours=self.session_ttl_hours)
            session_entity.last_seen_at = now
            session_entity.expires_at = next_expiry
            db.commit()
            return {
                "session_id": int(session_entity.id),
                "user": {
                    "id": int(user_entity.id),
                    "username": user_entity.username,
                    "role": self._normalize_role(user_entity.role),
                },
                "expires_at": next_expiry.isoformat(),
            }

    def revoke_session(self, *, session_token: str | None) -> None:
        token = str(session_token or "").strip()
        if not token:
            return
        token_hash = self._session_token_hash(token)
        with self.SessionLocal() as db:
            session_entity = db.scalar(
                select(AuthSessionEntity)
                .where(
                    AuthSessionEntity.session_token_hash == token_hash,
                    AuthSessionEntity.revoked_at.is_(None),
                )
                .limit(1)
            )
            if session_entity is None:
                return
            session_entity.revoked_at = self._now()
            db.commit()

    def reset_for_tests(self) -> None:
        with self.SessionLocal() as db:
            db.execute(delete(AuthLoginAttemptEntity))
            db.execute(delete(AuthSessionEntity))
            db.execute(delete(AuthUserEntity))
            db.commit()


AuthStore = FileAuthStore | DatabaseAuthStore
_auth_store_cache: dict[str, AuthStore] = {}


def clear_auth_store_cache() -> None:
    for store in _auth_store_cache.values():
        store.dispose()
    _auth_store_cache.clear()


def get_auth_store(settings: Settings) -> AuthStore:
    if settings.uses_database_auth_storage:
        cache_key = f"database:{settings.database_url}"
        store = _auth_store_cache.get(cache_key)
        if store is None:
            store = DatabaseAuthStore(
                database_url=settings.database_url,
                session_ttl_hours=settings.auth_session_ttl_hours,
            )
            _auth_store_cache[cache_key] = store
        return store

    cache_key = f"file:{Path(settings.auth_db_path).resolve()}"
    store = _auth_store_cache.get(cache_key)
    if store is None:
        store = FileAuthStore(
            db_path=settings.auth_db_path,
            session_ttl_hours=settings.auth_session_ttl_hours,
        )
        _auth_store_cache[cache_key] = store
    return store

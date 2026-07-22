from __future__ import annotations

from typing import Any, Dict, List, Optional

from crypto_utils import decrypt_field, encrypt_field
from security_sanitizer import redact_sensitive_text


class FubonAccountRepository:
    def __init__(self, db):
        self._db = db

    @staticmethod
    def _with_decrypted_secrets(row: Dict[str, Any] | None) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        result = {
            key: value for key, value in row.items()
            if key not in {"password_enc", "cert_password_enc", "api_key_enc"}
        }
        return {
            **result,
            "is_active": bool(row.get("is_active")),
            "is_enabled": bool(row.get("is_enabled")),
            "password": decrypt_field(row.get("password_enc")),
            "cert_password": decrypt_field(row.get("cert_password_enc")),
            "api_key": decrypt_field(row.get("api_key_enc")),
        }

    @staticmethod
    def _public_row(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id"),
            "label": row.get("label"),
            "user_id": row.get("user_id"),
            "cert_path": row.get("cert_path"),
            "ws_mode": row.get("ws_mode"),
            "is_active": bool(row.get("is_active")),
            "is_enabled": bool(row.get("is_enabled")),
            "has_password": True,
            "has_cert_password": bool(row.get("has_cert_password")),
            "has_api_key": True,
            "connection_status": row.get("connection_status"),
            "connection_error": redact_sensitive_text(row.get("connection_error")),
            "last_connected_at": row.get("last_connected_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    async def list_accounts(self) -> List[Dict[str, Any]]:
        rows = await self._db._fetchall(
            """
            SELECT
                id,
                label,
                user_id,
                cert_path,
                (cert_password_enc IS NOT NULL AND cert_password_enc <> '') AS has_cert_password,
                ws_mode,
                is_active,
                is_enabled,
                connection_status,
                connection_error,
                last_connected_at,
                created_at,
                updated_at
            FROM fubon_api_accounts
            ORDER BY is_active DESC, id ASC
            """
        )
        return [self._public_row(row) for row in rows]

    async def list_statuses(self) -> List[Dict[str, Any]]:
        rows = await self._db._fetchall(
            """
            SELECT id, label, is_active, is_enabled, connection_status,
                   connection_error, last_connected_at
            FROM fubon_api_accounts
            ORDER BY is_active DESC, id ASC
            """
        )
        return [
            {
                **row,
                "is_active": bool(row.get("is_active")),
                "is_enabled": bool(row.get("is_enabled")),
                "connection_error": redact_sensitive_text(row.get("connection_error")),
            }
            for row in rows
        ]

    async def get_account_with_secrets(self, account_id: int) -> Optional[Dict[str, Any]]:
        row = await self._db._fetchone(
            "SELECT * FROM fubon_api_accounts WHERE id=%s",
            (account_id,),
        )
        return self._with_decrypted_secrets(row)

    async def get_active_account(self) -> Optional[Dict[str, Any]]:
        row = await self._db._fetchone(
            """
            SELECT *
            FROM fubon_api_accounts
            WHERE is_active=1 AND is_enabled=1
            ORDER BY id ASC
            LIMIT 1
            """
        )
        return self._with_decrypted_secrets(row)

    async def list_enabled_accounts_with_secrets(self) -> List[Dict[str, Any]]:
        rows = await self._db._fetchall(
            """
            SELECT *
            FROM fubon_api_accounts
            WHERE is_enabled=1
            ORDER BY is_active DESC, id ASC
            """
        )
        return [item for item in (self._with_decrypted_secrets(row) for row in rows) if item]

    async def create_account(self, data: Dict[str, Any]) -> int:
        return await self._db._execute_insert(
            """
            INSERT INTO fubon_api_accounts
                (label, user_id, password_enc, cert_path, cert_password_enc,
                 api_key_enc, ws_mode, is_active, is_enabled)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                data["label"],
                data["user_id"],
                encrypt_field(data["password"]),
                data.get("cert_path") or "",
                encrypt_field(data.get("cert_password") or ""),
                encrypt_field(data["api_key"]),
                data.get("ws_mode") or "Speed",
                0,
                1 if data.get("is_enabled", True) else 0,
            ),
        )

    async def update_account(self, account_id: int, data: Dict[str, Any]) -> int:
        updates: list[str] = []
        params: list[Any] = []

        for key in ("label", "user_id", "cert_path", "ws_mode"):
            if key in data:
                updates.append(f"`{key}`=%s")
                params.append(data[key] or "")

        if "is_enabled" in data:
            updates.append("`is_enabled`=%s")
            params.append(1 if data["is_enabled"] else 0)

        if data.get("password"):
            updates.append("`password_enc`=%s")
            params.append(encrypt_field(data["password"]))
        if data.get("cert_password"):
            updates.append("`cert_password_enc`=%s")
            params.append(encrypt_field(data["cert_password"]))
        if data.get("api_key"):
            updates.append("`api_key_enc`=%s")
            params.append(encrypt_field(data["api_key"]))

        if not updates:
            return 0

        params.append(account_id)
        return await self._db._execute(
            f"UPDATE fubon_api_accounts SET {', '.join(updates)} WHERE id=%s",
            tuple(params),
        )

    async def delete_account(self, account_id: int) -> int:
        return await self._db._execute(
            "DELETE FROM fubon_api_accounts WHERE id=%s",
            (account_id,),
        )

    async def activate_account(self, account_id: int) -> bool:
        row = await self._db._fetchone(
            "SELECT id FROM fubon_api_accounts WHERE id=%s AND is_enabled=1",
            (account_id,),
        )
        if not row:
            return False
        await self._db._execute("UPDATE fubon_api_accounts SET is_active=0")
        await self._db._execute(
            "UPDATE fubon_api_accounts SET is_active=1 WHERE id=%s",
            (account_id,),
        )
        return True

    async def update_connection_status(
        self,
        account_id: int,
        status: str,
        error: str | None = None,
    ) -> None:
        if status == "connected":
            await self._db._execute(
                """
                UPDATE fubon_api_accounts
                SET connection_status=%s,
                    connection_error=NULL,
                    last_connected_at=NOW()
                WHERE id=%s
                """,
                (status, account_id),
            )
            return

        await self._db._execute(
            """
            UPDATE fubon_api_accounts
            SET connection_status=%s,
                connection_error=%s
            WHERE id=%s
            """,
            (status, redact_sensitive_text(error), account_id),
        )

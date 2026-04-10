from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import db
from repositories.fubon_accounts import FubonAccountRepository


router = APIRouter(prefix="/api/settings", tags=["settings"])


class FubonAccountCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    user_id: str = Field(..., min_length=5, max_length=50)
    password: str = Field(..., min_length=1)
    cert_path: Optional[str] = Field(default=None, max_length=500)
    cert_password: Optional[str] = None
    api_key: str = Field(..., min_length=10)
    ws_mode: str = Field(default="Speed", pattern="^(Speed|Normal)$")
    is_enabled: bool = True


class FubonAccountUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=100)
    user_id: Optional[str] = Field(default=None, min_length=5, max_length=50)
    password: Optional[str] = None
    cert_path: Optional[str] = Field(default=None, max_length=500)
    cert_password: Optional[str] = None
    api_key: Optional[str] = None
    ws_mode: Optional[str] = Field(default=None, pattern="^(Speed|Normal)$")
    is_enabled: Optional[bool] = None


@router.get("/fubon-accounts")
async def list_fubon_accounts():
    repo = FubonAccountRepository(db)
    return {"accounts": await repo.list_accounts()}


@router.post("/fubon-accounts", status_code=201)
async def create_fubon_account(body: FubonAccountCreate):
    repo = FubonAccountRepository(db)
    try:
        account_id = await repo.create_account(body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    return {"id": account_id, "message": "帳號已建立"}


@router.get("/fubon-accounts/status")
async def get_fubon_accounts_status():
    repo = FubonAccountRepository(db)
    return {"accounts": await repo.list_statuses()}


@router.put("/fubon-accounts/{account_id}")
async def update_fubon_account(account_id: int, body: FubonAccountUpdate):
    repo = FubonAccountRepository(db)
    try:
        updated = await repo.update_account(account_id, body.model_dump(exclude_none=True))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    if updated == 0:
        raise HTTPException(404, "帳號不存在或沒有變更")
    return {"message": "帳號已更新"}


@router.delete("/fubon-accounts/{account_id}")
async def delete_fubon_account(account_id: int):
    repo = FubonAccountRepository(db)
    deleted = await repo.delete_account(account_id)
    if deleted == 0:
        raise HTTPException(404, "帳號不存在")
    return {"message": "帳號已刪除"}


@router.post("/fubon-accounts/{account_id}/activate")
async def activate_fubon_account(account_id: int):
    from providers import fubon_manager

    repo = FubonAccountRepository(db)
    account = await repo.get_account_with_secrets(account_id)
    if not account:
        raise HTTPException(404, "帳號不存在")
    if not account.get("is_enabled"):
        raise HTTPException(400, "帳號已停用")

    activated = await repo.activate_account(account_id)
    if not activated:
        raise HTTPException(404, "帳號不存在或已停用")

    success = await fubon_manager.hot_switch(account)
    return {
        "success": success,
        "message": "已設為使用中" if success else "已設為使用中，但 SDK 連線尚未成功",
    }


@router.post("/fubon-accounts/{account_id}/test")
async def test_fubon_account(account_id: int):
    from fubon_provider import test_fubon_login

    repo = FubonAccountRepository(db)
    account = await repo.get_account_with_secrets(account_id)
    if not account:
        raise HTTPException(404, "帳號不存在")

    await repo.update_connection_status(account_id, "connecting")
    result = await test_fubon_login(account)
    await repo.update_connection_status(
        account_id,
        "connected" if result.get("success") else "error",
        None if result.get("success") else result.get("message"),
    )
    return result

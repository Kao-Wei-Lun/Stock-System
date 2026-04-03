"""Alert & notification routes."""

from fastapi import APIRouter, HTTPException, Query

from database import DEFAULT_OWNER_ID, db
from schemas import (
    AlertCreatePayload,
    AlertUpdatePayload,
    NotificationReadStatePayload,
)

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts")
async def list_alerts():
    return {"items": await db.list_alerts(owner_id=DEFAULT_OWNER_ID)}


@router.post("/alerts")
async def create_alert(payload: AlertCreatePayload):
    try:
        return await db.create_alert(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/alerts/{alert_id}")
async def update_alert(alert_id: int, payload: AlertUpdatePayload):
    try:
        alert = await db.update_alert(
            alert_id,
            payload.model_dump(exclude_unset=True),
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not alert:
        raise HTTPException(404, "Alert not found")
    return alert


@router.get("/alerts/{alert_id}/triggers")
async def get_alert_trigger_logs(alert_id: int, limit: int = Query(20, ge=1, le=200)):
    alert = await db.get_alert(alert_id, owner_id=DEFAULT_OWNER_ID)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return {"items": await db.list_alert_trigger_logs(alert_id, owner_id=DEFAULT_OWNER_ID, limit=limit)}


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    deleted = await db.delete_alert(alert_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Alert not found")
    return {"ok": True, "alert_id": alert_id}


# ─── Notifications ───────────────────────────────────────────

@router.get("/notifications")
async def list_notifications(
    unread_only: bool = Query(False, description="Only unread notifications"),
    limit: int = Query(50, ge=1, le=200),
):
    return {
        "items": await db.list_notifications(
            owner_id=DEFAULT_OWNER_ID,
            unread_only=unread_only,
            limit=limit,
        )
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int):
    notification = await db.mark_notification_read(notification_id, owner_id=DEFAULT_OWNER_ID)
    if not notification:
        raise HTTPException(404, "Notification not found")
    return notification


@router.patch("/notifications/{notification_id}/read")
async def patch_notification_read_state(notification_id: int, payload: NotificationReadStatePayload):
    notification = await db.set_notification_read_state(notification_id, payload.read, owner_id=DEFAULT_OWNER_ID)
    if not notification:
        raise HTTPException(404, "Notification not found")
    return notification

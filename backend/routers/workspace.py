"""Workspace routes."""

from fastapi import APIRouter, HTTPException

from database import DEFAULT_OWNER_ID, db
from schemas import WorkspacePresetCreate, WorkspacePresetUpdate

router = APIRouter(prefix="/api", tags=["workspace"])


@router.get("/workspaces")
async def list_workspaces():
    return {"items": await db.list_workspace_presets(owner_id=DEFAULT_OWNER_ID)}


@router.post("/workspaces")
async def create_workspace(payload: WorkspacePresetCreate):
    try:
        return await db.create_workspace_preset(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: int):
    workspace = await db.get_workspace_preset(workspace_id, owner_id=DEFAULT_OWNER_ID)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    return workspace


@router.put("/workspaces/{workspace_id}")
async def update_workspace(workspace_id: int, payload: WorkspacePresetUpdate):
    try:
        workspace = await db.update_workspace_preset(
            workspace_id,
            payload.model_dump(exclude_unset=True),
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    return workspace


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: int):
    deleted = await db.delete_workspace_preset(workspace_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Workspace not found")
    return {"ok": True, "workspace_id": workspace_id}

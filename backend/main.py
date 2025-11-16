from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import create_document, get_documents, get_document, update_document, delete_document, get_db
from schemas import Note, Upload, Contributor, Settings

app = FastAPI(title="NoteBuddy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

ADMIN_USERNAME = "buddy"
ADMIN_PASSWORD = "buddy_mukesh123@"
ADMIN_TOKEN = "admin-token"


# Health & diagnostics
@app.get("/")
async def root():
    return {"message": "OK", "app": "NoteBuddy API"}


@app.get("/test")
async def test():
    try:
        db = get_db()
        colls = await db.list_collection_names()
        return {
            "backend": "fastapi",
            "database": "mongodb",
            "database_url": str(db.client.address) if hasattr(db.client, 'address') else "connected",
            "database_name": db.name,
            "connection_status": "connected",
            "collections": colls,
        }
    except Exception as e:
        return {"backend": "fastapi", "database": "mongodb", "connection_status": f"error: {e}"}


# Helpers
async def require_admin(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# Public routes
@app.get("/api/notes")
async def list_notes(q: Optional[str] = None, subject: Optional[str] = None, class_level: Optional[str] = None, college: Optional[str] = None, skip: int = 0, limit: int = 20):
    filt = {k:v for k,v in {
        "subject": subject,
        "class_level": class_level,
        "college": college,
    }.items() if v}
    items = await get_documents("note", filt, limit=limit, skip=skip, sort=[["created_at", -1]])
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i.get("title"," ").lower() or ql in i.get("subject"," ").lower()]
    return {"items": items, "skip": skip, "limit": limit}


@app.get("/api/notes/{note_id}")
async def get_note(note_id: str):
    note = await get_document("note", {"id": note_id})
    if not note:
        raise HTTPException(status_code=404, detail="Not found")
    return note


class UploadIn(Upload):
    pass


@app.post("/api/uploads")
async def create_upload(upload: UploadIn):
    data = upload.dict()
    data["status"] = "pending"
    doc = await create_document("upload", data)
    return {"message": "Received", "id": doc["id"]}


@app.get("/api/leaderboard")
async def leaderboard(limit: int = 10):
    items = await get_documents("contributor", {}, limit=limit, sort=[["points", -1]])
    return {"items": items}


@app.get("/api/settings")
async def get_settings():
    items = await get_documents("settings", {}, limit=1)
    if items:
        return items[0]
    default = Settings().dict()
    await create_document("settings", default)
    return default


# Admin routes
class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/admin/login")
async def admin_login(body: LoginBody):
    if body.username == ADMIN_USERNAME and body.password == ADMIN_PASSWORD:
        return {"token": ADMIN_TOKEN}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/api/admin/uploads")
async def admin_list_uploads(status: Optional[str] = None, skip: int = 0, limit: int = 50, _: bool = Depends(require_admin)):
    filt = {"status": status} if status else {}
    items = await get_documents("upload", filt, limit=limit, skip=skip, sort=[["created_at", -1]])
    return {"items": items}


class AcceptBody(BaseModel):
    assigned_points: int = 0


@app.post("/api/admin/uploads/{upload_id}/accept")
async def accept_upload(upload_id: str, body: AcceptBody, _: bool = Depends(require_admin)):
    upload = await get_document("upload", {"id": upload_id})
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    note_data = {k: upload.get(k) for k in ["title","subject","class_level","college","tags","pages","drive_link"]}
    await create_document("note", note_data)
    await update_document("upload", {"id": upload_id}, {"status": "accepted"})
    name = upload.get("contributor_name")
    if name:
        contrib = await get_document("contributor", {"name": name})
        if contrib:
            await update_document("contributor", {"id": contrib["id"]}, {"points": int(contrib.get("points",0)) + int(body.assigned_points)})
        else:
            await create_document("contributor", {"name": name, "points": body.assigned_points})
    return {"message": "Accepted"}


class RejectBody(BaseModel):
    reason: Optional[str] = None


@app.post("/api/admin/uploads/{upload_id}/reject")
async def reject_upload(upload_id: str, body: RejectBody, _: bool = Depends(require_admin)):
    upload = await get_document("upload", {"id": upload_id})
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    await update_document("upload", {"id": upload_id}, {"status": "rejected", "reviewer_note": body.reason})
    return {"message": "Rejected"}


@app.get("/api/admin/contributors")
async def list_contributors(skip: int = 0, limit: int = 100, _: bool = Depends(require_admin)):
    items = await get_documents("contributor", {}, limit=limit, skip=skip, sort=[["points", -1]])
    return {"items": items}


class ContributorIn(BaseModel):
    name: str
    points: int = 0


@app.post("/api/admin/contributors")
async def create_contributor(body: ContributorIn, _: bool = Depends(require_admin)):
    doc = await create_document("contributor", body.dict())
    return {"id": doc["id"]}


class AdjustPointsBody(BaseModel):
    id: str
    delta: int


@app.post("/api/admin/contributors/adjust-points")
async def adjust_points(body: AdjustPointsBody, _: bool = Depends(require_admin)):
    contrib = await get_document("contributor", {"id": body.id})
    if not contrib:
        raise HTTPException(status_code=404, detail="Contributor not found")
    new_points = int(contrib.get("points",0)) + int(body.delta)
    await update_document("contributor", {"id": body.id}, {"points": new_points})
    return {"message": "Updated", "points": new_points}


class SettingsIn(Settings):
    pass


@app.put("/api/admin/settings")
async def put_settings(body: SettingsIn, _: bool = Depends(require_admin)):
    existing = await get_documents("settings", {}, limit=1)
    if existing:
        _id = existing[0]["id"]
        await update_document("settings", {"id": _id}, body.dict())
        return {"message": "Updated"}
    await create_document("settings", body.dict())
    return {"message": "Created"}

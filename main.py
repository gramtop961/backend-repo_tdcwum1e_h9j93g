import os
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Note as NoteSchema, Upload as UploadSchema, Contributor as ContributorSchema, Settings as SettingsSchema

app = FastAPI(title="NoteBuddy API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_USER = os.getenv("ADMIN_USER", "buddy")
ADMIN_PASS = os.getenv("ADMIN_PASS", "buddy_mukesh123@")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-token")


class LoginRequest(BaseModel):
    username: str
    password: str


class AcceptPayload(BaseModel):
    assigned_points: int
    reviewer_note: Optional[str] = None


class RejectPayload(BaseModel):
    reason: str


class PointsAdjust(BaseModel):
    contributor_id: str
    delta: int
    note: Optional[str] = None


# Utilities

def require_admin(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1]
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return True


@app.get("/")
def read_root():
    return {"message": "NoteBuddy API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "❌ Not Set"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Public endpoints

@app.get("/api/notes")
def list_notes(
    q: Optional[str] = None,
    subject: Optional[str] = None,
    class_level: Optional[str] = Query(None, alias="class"),
    college: Optional[str] = None,
    sort: Optional[str] = "new",
    skip: int = 0,
    limit: int = 24,
):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    filter_q = {}
    if subject:
        filter_q["subject"] = subject
    if class_level:
        filter_q["class_level"] = class_level
    if college:
        filter_q["college"] = college
    if q:
        filter_q["title"] = {"$regex": q, "$options": "i"}

    sort_spec = [("created_at", -1)]
    if sort == "likes":
        sort_spec = [("likes", -1)]
    elif sort == "downloads":
        sort_spec = [("downloads", -1)]

    cursor = db["note"].find(filter_q).sort(sort_spec).skip(skip).limit(limit)
    items = []
    for d in cursor:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return {"items": items, "count": len(items)}


@app.get("/api/notes/{note_id}")
def get_note(note_id: str):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    try:
        d = db["note"].find_one({"_id": ObjectId(note_id)})
        if not d:
            raise HTTPException(404, detail="Note not found")
        d["id"] = str(d.pop("_id"))
        return d
    except Exception:
        raise HTTPException(400, detail="Invalid note id")


@app.post("/api/uploads")
def submit_upload(payload: UploadSchema):
    # Public submission goes to pending review queue
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    data = payload.dict()
    data["status"] = data.get("status", "pending")
    new_id = create_document("upload", data)
    return {"ok": True, "id": new_id, "message": "Thanks — Notes received! Your Knowledge Points will be reviewed."}


@app.get("/api/leaderboard")
def leaderboard(limit: int = 20):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    cursor = db["contributor"].find({}).sort([("points", -1)]).limit(limit)
    items = []
    for d in cursor:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return {"items": items}


# Admin endpoints

@app.post("/api/admin/login")
def admin_login(body: LoginRequest):
    if body.username == ADMIN_USER and body.password == ADMIN_PASS:
        return {"token": ADMIN_TOKEN, "user": {"name": "Admin", "role": "admin"}}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/api/admin/uploads")
def admin_list_uploads(status: Optional[str] = None, _: bool = Depends(require_admin)):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    q = {}
    if status:
        q["status"] = status
    cursor = db["upload"].find(q).sort([("created_at", -1)])
    items = []
    for d in cursor:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return {"items": items}


@app.post("/api/admin/uploads/{upload_id}/accept")
def accept_upload(upload_id: str, body: AcceptPayload, _: bool = Depends(require_admin)):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    try:
        up = db["upload"].find_one({"_id": ObjectId(upload_id)})
        if not up:
            raise HTTPException(404, detail="Upload not found")
        # Create Note from Upload
        note_data = {
            "title": up.get("title"),
            "class_level": up.get("class_level"),
            "college": up.get("college"),
            "subject": up.get("subject"),
            "chapters": up.get("chapters", []),
            "pages": up.get("pages"),
            "drive_link": up.get("drive_link"),
            "uploader_alias": up.get("contributor_name") or "Admin Upload",
            "contributor_id": None,
            "thumbnail_url": up.get("thumbnail_url"),
            "likes": 0,
            "downloads": 0,
            "language": "en"
        }
        # validate
        NoteSchema(**note_data)
        new_note_id = create_document("note", note_data)
        # Update upload
        db["upload"].update_one({"_id": ObjectId(upload_id)}, {"$set": {"status": "accepted", "assigned_points": body.assigned_points, "reviewer_note": body.reviewer_note}})
        # Award points if contributor exists by name
        name = up.get("contributor_name")
        if name:
            c = db["contributor"].find_one({"name": name})
            if c:
                db["contributor"].update_one({"_id": c["_id"]}, {"$inc": {"points": body.assigned_points}})
        return {"ok": True, "note_id": new_note_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, detail=f"Error accepting upload: {str(e)}")


@app.post("/api/admin/uploads/{upload_id}/reject")
def reject_upload(upload_id: str, body: RejectPayload, _: bool = Depends(require_admin)):
    if db is None:
        raise HTTPException(500, detail="Database not configured")
    try:
        db["upload"].update_one({"_id": ObjectId(upload_id)}, {"$set": {"status": "rejected", "reviewer_note": body.reason}})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, detail=f"Error rejecting upload: {str(e)}")


@app.get("/api/admin/contributors")
def list_contributors(_: bool = Depends(require_admin)):
    cursor = db["contributor"].find({}).sort([("points", -1)])
    items = []
    for d in cursor:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return {"items": items}


@app.post("/api/admin/contributors")
def upsert_contributor(c: ContributorSchema, _: bool = Depends(require_admin)):
    existing = db["contributor"].find_one({"name": c.name})
    if existing:
        db["contributor"].update_one({"_id": existing["_id"]}, {"$set": c.dict()})
        return {"id": str(existing["_id"]) }
    new_id = create_document("contributor", c)
    return {"id": new_id}


@app.post("/api/admin/contributors/adjust-points")
def adjust_points(body: PointsAdjust, _: bool = Depends(require_admin)):
    try:
        db["contributor"].update_one({"_id": ObjectId(body.contributor_id)}, {"$inc": {"points": body.delta}})
        return {"ok": True}
    except Exception:
        raise HTTPException(400, detail="Invalid contributor id")


@app.get("/api/settings")
def get_settings():
    s = db["settings"].find_one({})
    if not s:
        default = SettingsSchema()
        sid = create_document("settings", default)
        s = db["settings"].find_one({"_id": ObjectId(sid)})
    s["id"] = str(s.pop("_id"))
    return s


@app.put("/api/admin/settings")
def update_settings(body: SettingsSchema, _: bool = Depends(require_admin)):
    s = db["settings"].find_one({})
    if not s:
        sid = create_document("settings", body)
        return {"id": sid}
    db["settings"].update_one({"_id": s["_id"]}, {"$set": body.dict()})
    return {"id": str(s["_id"]) }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "notebuddy")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(DATABASE_URL)
        _db = _client[DATABASE_NAME]
    return _db


def _ensure_id_filter(filter_dict: Dict[str, Any]) -> Dict[str, Any]:
    # Allow filtering by "id" string by mapping to _id ObjectId
    f = dict(filter_dict)
    if "id" in f:
        try:
            f["_id"] = ObjectId(f.pop("id"))
        except Exception:
            # keep as-is; may not match anything
            f.pop("id", None)
    return f


async def create_document(collection: str, data: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    now = datetime.utcnow().isoformat()
    doc = {**data, "created_at": now, "updated_at": now}
    res = await db[collection].insert_one(doc)
    oid = res.inserted_id
    # also store readable id field for convenience
    await db[collection].update_one({"_id": oid}, {"$set": {"id": str(oid)}})
    doc["_id"] = oid
    doc["id"] = str(oid)
    return _normalize(doc)


async def update_document(collection: str, filter_dict: Dict[str, Any], update_data: Dict[str, Any]) -> int:
    db = get_db()
    update_data["updated_at"] = datetime.utcnow().isoformat()
    filt = _ensure_id_filter(filter_dict)
    res = await db[collection].update_one(filt, {"$set": update_data})
    return res.modified_count


async def get_documents(collection: str, filter_dict: Optional[Dict[str, Any]] = None, limit: int = 20, skip: int = 0, sort: Optional[List] = None) -> List[Dict[str, Any]]:
    db = get_db()
    filt = _ensure_id_filter(filter_dict or {})
    cursor = db[collection].find(filt).skip(skip).limit(limit)
    if sort:
        cursor = cursor.sort(sort)
    items = []
    async for doc in cursor:
        items.append(_normalize(doc))
    return items


async def get_document(collection: str, filter_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    db = get_db()
    filt = _ensure_id_filter(filter_dict)
    doc = await db[collection].find_one(filt)
    return _normalize(doc) if doc else None


async def delete_document(collection: str, filter_dict: Dict[str, Any]) -> int:
    db = get_db()
    filt = _ensure_id_filter(filter_dict)
    res = await db[collection].delete_one(filt)
    return res.deleted_count


def _normalize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    d = {**doc}
    if "_id" in d:
        d["id"] = d.get("id") or str(d["_id"])  # ensure id exists
        d.pop("_id", None)
    return d

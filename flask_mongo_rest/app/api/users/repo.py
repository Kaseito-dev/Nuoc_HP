
from typing import Optional, Dict, Any, List, Tuple
import uuid
from ...extensions import get_db
from ...utils.bson import to_object_id, oid_str
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from bson import ObjectId
from pymongo import ASCENDING, errors, ReturnDocument
from werkzeug.exceptions import NotFound, Conflict

COL = "users"


def _oid_str(v) -> str:
    return str(v) if isinstance(v, ObjectId) else v

def db_to_api(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return None
    out = {
        "id": str(doc["_id"]),
        "username": doc.get("username"),
        "role_name": doc.get("role_name"),
        "branch_id": str(doc["branch_id"]) if doc.get("branch_id") else None,
        "company_id": str(doc["company_id"]) if doc.get("company_id") else None,
        "is_active": bool(doc.get("is_active", True)),
    }
    return out

def find_role_by_name(role_name: str) -> Dict[str, Any]:
    db = get_db()
    role = db.roles.find_one({"role_name": role_name})
    if not role:
        raise NotFound(f"Role '{role_name}' not found")
    return role

def username_exists(username: str) -> bool:
    db = get_db()
    return db[COL].find_one({"username": username}) is not None

def username_taken_by_other(user_name: str, exclude_user_id: str) -> bool:
    db = get_db()
    return db[COL].find_one({
        "username": user_name,
        "_id": {"$ne": _oid_str(exclude_user_id)}
    }) is not None

def insert_user(username: str, password_hash: str, role_id: ObjectId,
                role_name: str, is_active: bool = True) -> Dict[str, Any]:
    db = get_db()

    if username_exists(username):
        raise Conflict("Username already exists")

    doc = {
        "username": username,
        "password": password_hash,
        "role_id": role_id,
        "role_name": role_name,         # lưu kèm role_name để khỏi join khi đọc
        "is_active": is_active,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
    }
    try:
        res = db[COL].insert_one(doc)
    except errors.DuplicateKeyError as e:
        raise Conflict("Username already exists") from e

    return {
        "id": _oid_str(res.inserted_id),
        "username": username,
        "role_name": role_name,
        "is_active": is_active,
    }

def find_by_id(uid: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        doc = db[COL].find_one({"_id": to_object_id(uid)})
    except Exception:
        return None
    if not doc: return None
    doc["id"] = oid_str(doc.pop("_id"))
    return doc


def _build_filter(q: Optional[str]) -> Dict[str, Any]:
    if not q:
        return {}
    return {
        "$or": [
            {"name":  {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]
    }

def _build_sort(sort: Optional[str]):
    if not sort:
        return [("_id", 1)]
    field = sort.lstrip("-")
    direction = -1 if sort.startswith("-") else 1
    return [(field, direction)]

def list_users_paginated(page: int, page_size: int, q: Optional[str], sort: Optional[str]) -> Tuple[List[Dict[str, Any]], bool]:
    db = get_db()
    flt = _build_filter(q)
    srt = _build_sort(sort)
    skip = (page - 1) * page_size
    cur = db[COL].find(flt).sort(srt).skip(skip).limit(page_size + 1)
    out = []
    for d in cur:
        d["id"] = oid_str(d.pop("_id"))
        out.append(d)
    has_next = len(out) > page_size
    if has_next:
        out = out[:page_size]
    return out, has_next

def update_user(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    print("Úer ID to update:", user_id)

    user = db[COL].find_one({"_id": ObjectId(user_id)})
    print("Current user data:", user)
    if not user:
        print("User not found in update_user")
        raise NotFound("User not found")

    print("Line 125 reached in repo.py with updates:", updates)
    doc = db[COL].find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": updates, "$currentDate": {"updated_at": True}},
        return_document=ReturnDocument.AFTER
    )
    return db_to_api(doc)


def delete_user(uid: str) -> bool:
    db = get_db()
    try:
        res = db[COL].delete_one({"_id": to_object_id(uid)})
    except Exception:
        return False
    return res.deleted_count == 1

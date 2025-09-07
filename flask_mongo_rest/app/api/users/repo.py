
from typing import Optional, Dict, Any, List, Tuple
from ...extensions import get_db
from ...utils.bson import to_object_id, oid_str

COLLECTION = "users"

def insert_user(doc: Dict[str, Any]) -> str:
    db = get_db()
    res = db[COLLECTION].insert_one(doc)
    return oid_str(res.inserted_id)

def find_by_id(uid: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        doc = db[COLLECTION].find_one({"_id": to_object_id(uid)})
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
    cur = db[COLLECTION].find(flt).sort(srt).skip(skip).limit(page_size + 1)
    out = []
    for d in cur:
        d["id"] = oid_str(d.pop("_id"))
        out.append(d)
    has_next = len(out) > page_size
    if has_next:
        out = out[:page_size]
    return out, has_next

def update_user(uid: str, patch: Dict[str, Any]) -> bool:
    db = get_db()
    try:
        res = db[COLLECTION].update_one({"_id": to_object_id(uid)}, {"$set": patch})
    except Exception:
        return False
    return res.matched_count == 1

def delete_user(uid: str) -> bool:
    db = get_db()
    try:
        res = db[COLLECTION].delete_one({"_id": to_object_id(uid)})
    except Exception:
        return False
    return res.deleted_count == 1

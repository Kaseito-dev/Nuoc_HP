
import bcrypt as bc
from flask_jwt_extended import get_jwt
from werkzeug.exceptions import Forbidden, BadRequest , Conflict
from typing import Dict, Any
from bson import ObjectId
from .schemas import UserCreate, UserOut, UserUpdate
from . import repo

def _role_name() -> str | None:
    claims = get_jwt()
    return claims.get("role_name") if claims else None

def _hash_password(plain: str) -> str:
    return bc.hashpw(plain.encode("utf-8"), bc.gensalt()).decode("utf-8")

def create_user_admin_only(data: UserCreate) -> UserOut:
    if _role_name() != "admin":
        raise Forbidden("Only admin can create users")

    role = repo.find_role_by_name(data.role_name)
    out = repo.insert_user(
        username=data.user_name,
        password_hash=_hash_password(data.password_user),
        role_id=role["_id"],
        role_name=role["role_name"],
    )
    return UserOut(**out)

def get_user(uid: str):
    return repo.find_by_id(uid)

def list_user(page: int, page_size: int, q: str | None, sort: str | None):
    return repo.list_users_paginated(page, page_size, q, sort)

def update_user_admin_only(user_id: str, data: UserUpdate) -> UserOut:
    print(f"Attempting to update user {user_id} with data: {data}")
    if _role_name() != "admin":
        raise Forbidden("Only admin can update users")

    updates: Dict[str, Any] = {}
    print("Line 42 reached")
    # if data.user_name is not None:
    #     # kiểm tra trùng username với user khác
    if repo.username_taken_by_other(data.user_name, user_id):
        updates["username"] = data.user_name

    if data.password is not None:
        updates["password"] = _hash_password(data.password)

    print('Line 51 reached')
    if data.role_name is not None:
        role = repo.find_role_by_name(data.role_name)
        updates["role_id"] = role["_id"]
        updates["role_name"] = role["role_name"]

    if not updates:
        raise BadRequest("No valid fields to update")

    print("Line 60 reached, updates to apply:", updates)
    out = repo.update_user(user_id, updates)
    print("Update result:", out)
    return UserOut(**out)

def remove_user(uid: str):
    return repo.delete_user(uid)

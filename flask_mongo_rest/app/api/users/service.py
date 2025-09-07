
from .schemas import UserCreate, UserUpdate
from . import repo
from ...errors import BadRequest, Conflict



def get_user(uid: str):
    return repo.find_by_id(uid)

def list_user(page: int, page_size: int, q: str | None, sort: str | None):
    return repo.list_users_paginated(page, page_size, q, sort)

def update_user_info(uid: str, data: UserUpdate):
    patch = {k: v for k, v in data.model_dump().items() if v is not None}
    if not patch:
        raise BadRequest("No fields to update")
    ok = repo.update_user(uid, patch)
    return ok and repo.find_by_id(uid)

def remove_user(uid: str):
    return repo.delete_user(uid)

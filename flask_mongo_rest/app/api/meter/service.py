from typing import Optional
from flask_jwt_extended import get_jwt_identity
from ...extensions import get_db
from ...utils.bson import to_object_id, oid_str
from ...errors import BadRequest
from .schemas import MeterCreate, MeterUpdate, MeterOut
from werkzeug.exceptions import NotFound, Conflict, Forbidden
from datetime import datetime
from . import repo
from flask_jwt_extended import get_jwt

def _get_user_scope():
    claims = get_jwt()
    company_id = claims.get("company_id")
    branch_id  = claims.get("branch_id")
    role_id    = claims.get("role_id")
    return company_id, branch_id, role_id

def _branch_ids_in_company(company_id):
    db = get_db()
    return [oid_str(b["_id"]) for b in db.branches.find({"company_id": company_id}, {"_id":1})]

def _role_name() -> str:
    claims = get_jwt()
    return claims.get("role_name")

def create_meter_admin_only(data: MeterCreate) -> MeterOut:
    print("Creating meter with data:", data)
    if _role_name() != "admin":
        raise Forbidden("Only admin can create meter")

    branch = repo.find_branch_by_name(data.branch_name)  # dùng data.branch_name

    if repo.exists_meter_by_branchid_meterid(
        branch["_id"], repo._meter_id_from_name(data.meter_name)
    ):
        print(repo.exists_meter_by_branchid_meterid(
        branch["_id"], repo._meter_id_from_name(data.meter_name)
    ))
        raise Conflict(
            f"Meter '{data.meter_name}' already exists in branch '{branch['name']}'"
        )

    doc = repo.insert_meter(branch["_id"], data.meter_name, data.installation_time)
    doc["branch_name"] = branch["name"]
    return MeterOut(**doc)

def get_meter(mid: str):
    company_id, branch_id, role_id = _get_user_scope()
    m = repo.get(mid)
    if not m: return None
    # if branch_id and m["branch_id"] != oid_str(branch_id):
    #     return None
    if company_id and not branch_id:
        if m["branch_id"] not in _branch_ids_in_company(company_id):
            return None
    return m

def list_meters(page:int, page_size:int, q: Optional[str], sort: Optional[str]):
    company_id, branch_id, role_id = _get_user_scope()
    if branch_id:
        return repo.list_paginated(page, page_size, [oid_str(branch_id)], q, sort)
    if company_id:
        branches = _branch_ids_in_company(company_id)
        return repo.list_paginated(page, page_size, branches, q, sort)
    # admin: không giới hạn
    return repo.list_paginated(page, page_size, None, q, sort)

def update_meter(mid: str, data: MeterUpdate):
    company_id, branch_id, role_id = _get_user_scope()
    cur = repo.get(mid)
    if not cur: return None
    if branch_id and cur["branch_id"] != oid_str(branch_id):
        raise BadRequest("Not allowed to update another branch's meter")
    if company_id and not branch_id:
        if cur["branch_id"] not in _branch_ids_in_company(company_id):
            raise BadRequest("Not allowed to update outside your company")
    patch = {k:v for k,v in data.model_dump().items() if v is not None}
    if not patch:
        raise BadRequest("No fields to update")
    ok = repo.update(mid, patch)
    return ok and repo.get(mid)

def remove_meter(mid: str):
    company_id, branch_id, role_id = _get_user_scope()
    cur = repo.get(mid)
    if not cur: return False
    if branch_id and cur["branch_id"] != oid_str(branch_id):
        return False
    if company_id and not branch_id:
        if cur["branch_id"] not in _branch_ids_in_company(company_id):
            return False
    return repo.delete(mid)

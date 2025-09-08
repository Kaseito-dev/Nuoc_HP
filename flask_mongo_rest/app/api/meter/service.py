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
    role_name  = claims.get("role_name")
    return company_id, branch_id, role_id, role_name

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
    # Lấy quyền từ JWT
    company_id, branch_id, role_id, role_name = _get_user_scope()
  

    # 1) Chỉ admin được cập nhật
    if role_name != "admin":
        raise Forbidden("Only admin can update meter")

    # 2) Lấy meter hiện tại
    cur = repo.get(mid)
    print("Current meter data:", cur)
    if not cur:
        raise NotFound("Meter not found")

    # 3) Gom patch từ các field có giá trị
    patch = {k: v for k, v in data.model_dump().items() if v is not None}
    if not patch:
        raise BadRequest("No fields to update")

    # 4) Nếu đổi chi nhánh bằng branch_name → map sang branch_id (ObjectId)
    if "branch_name" in patch:
        branch = repo.find_branch_by_name(patch["branch_name"])
        patch["branch_id"] = branch["_id"]      # repo.update sẽ nhận ObjectId
        del patch["branch_name"]

    # Xác định branch_id mục tiêu để check trùng tên (branch mới nếu có, nếu không giữ branch hiện tại)
    target_branch_id = patch.get("branch_id") or cur["branch_id"]

    # 5) Nếu đổi meter_name → phải kiểm tra trùng trong branch mục tiêu + sinh meter_id mới
    if "meter_name" in patch:
        new_meter_name = patch["meter_name"].strip()
        new_meter_id = repo._meter_id_from_name(new_meter_name)

        # Nếu tên/ID mới trùng với meter khác trong cùng branch → chặn
        # (Repo side: exists_* nên chấp nhận cả ObjectId/str cho branch_id)
        if repo.exists_meter_by_branchid_meterid(target_branch_id, new_meter_id):
            # nếu document trùng chính là bản thân mid hiện tại thì không sao,
            # còn nếu là meter khác thì Conflict
            if not (cur.get("meter_id") == new_meter_id and cur.get("branch_id") == str(target_branch_id)):
                raise Conflict("Meter name already exists in this branch")

        patch["meter_name"] = new_meter_name
        patch["meter_id"] = new_meter_id

    # 6) Cập nhật DB
    ok = repo.update(mid, patch)   # nên trả True/False hoặc doc sau update
    if not ok:
        raise BadRequest("Update failed")

    # 7) Trả lại meter sau khi cập nhật
    return repo.get(mid)

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

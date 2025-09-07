

import os
from datetime import datetime
import bcrypt as bc
from pymongo import MongoClient, ASCENDING, ReturnDocument
from typing import Optional, Dict, Any, List, Set

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB  = os.getenv("MONGO_DB", "Nuoc_HP")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]


def reset_collections():
    print("Resetting collections...")
    for col in ["companies", "branches", "meters", "users", "roles", "permissions", "role_permissions"]:
        db[col].drop()

    # Xóa toàn bộ index mặc định (trừ _id_)
    for col_name in db.list_collection_names():
        indexes = db[col_name].index_information()
        for idx in indexes:
            if idx != "_id_":
                db[col_name].drop_index(idx)

def hash_password(plain: str) -> str:
    return bc.hashpw(plain.encode("utf-8"), bc.gensalt()).decode("utf-8")

def upsert(collection: str, query: Dict[str, Any], doc: Dict[str, Any]):
    return db[collection].find_one_and_update(
        query, {"$setOnInsert": doc}, upsert=True, return_document=ReturnDocument.AFTER
    )

def seed_permissions_roles():
    # ---- 1) Permissions (thêm quyền read) ----
    perms = [
        {"key": "branch:read",   "description": "Xem chi nhánh"},
        {"key": "branch:create", "description": "Tạo chi nhánh"},
        {"key": "branch:update", "description": "Sửa chi nhánh"},
        {"key": "branch:delete", "description": "Xóa chi nhánh"},
        {"key": "meter:read",    "description": "Xem đồng hồ"},
        {"key": "meter:create",  "description": "Tạo đồng hồ"},
        {"key": "meter:update",  "description": "Sửa đồng hồ"},
        {"key": "meter:delete",  "description": "Xóa đồng hồ"},
    ]
    for p in perms:
        upsert("permissions", {"key": p["key"]}, p)

    # ---- 2) Roles ----
    roles = [
        {"role_name": "admin"},
        {"role_name": "company_manager"},
        {"role_name": "branch_manager"},
    ]
    for r in roles:
        upsert("roles", {"role_name": r["role_name"]}, r)

    # ---- 3) Map role -> permissions ----
    perm_docs = {p["key"]: p for p in db.permissions.find({}, {"_id": 1, "key": 1})}
    role_docs = {r["role_name"]: r for r in db.roles.find({}, {"_id": 1, "role_name": 1})}

    def bind(role_name: str, perm_keys: List[str]):
        # validate keys
        missing = [k for k in perm_keys if k not in perm_docs]
        if missing:
            raise KeyError(f"Permission keys not found: {missing}")

        role_id = role_docs[role_name]["_id"]
        # xóa mapping cũ của role này để tránh trùng nếu seed nhiều lần
        db.role_permissions.delete_many({"role_id": role_id})
        # insert lại mapping
        rp_docs = [
            {"role_id": role_id, "perm_key": k, "permission_id": perm_docs[k]["_id"]}
            for k in perm_keys
        ]
        if rp_docs:
            db.role_permissions.insert_many(rp_docs)

    # Cấp quyền
    # admin: tất cả
    bind("admin", list(perm_docs.keys()))

    # company_manager: CRUD chi nhánh + read chi nhánh + read đồng hồ (theo scope công ty)
    bind("company_manager", [
        "branch:read", "branch:create", "branch:update", "branch:delete",
        "meter:read",
    ])

    # branch_manager: CRUD đồng hồ + read đồng hồ (chi nhánh của mình) + read chi nhánh (của mình)
    bind("branch_manager", [
        "meter:read", "meter:create", "meter:update", "meter:delete",
        "branch:read",
    ])
def seed_org():
    # Company
    comp = upsert("companies", {"name": "Công ty Cấp Nước Hải Phòng"},
                  {"name": "Công ty Cấp Nước Hải Phòng", "address": "Hải Phòng"})
    company_id = comp["_id"]

    # Branches
    branches = [
        {"company_id": company_id, "name": "Văn Đẩu",   "address": "Hải Phòng - Văn Đẩu"},
        {"company_id": company_id, "name": "Bắc Sơn",   "address": "Hải Phòng - Bắc Sơn"},
        {"company_id": company_id, "name": "Trường Sơn","address": "Hải Phòng - Trường Sơn"},
    ]
    ids = {}
    for b in branches:
        doc = upsert("branches", {"company_id": b["company_id"], "name": b["name"]}, b)
        ids[b["name"]] = doc["_id"]

    # Meters
    meters = [
        {"branch_id": ids["Văn Đẩu"],    "meter_name": "Đồng hồ Văn Đẩu 01", "installation_time": datetime(2023,5,10,8,0,0)},
        {"branch_id": ids["Văn Đẩu"],    "meter_name": "Đồng hồ Văn Đẩu 02", "installation_time": datetime(2023,6,12,8,0,0)},
        {"branch_id": ids["Bắc Sơn"],    "meter_name": "Đồng hồ Bắc Sơn 01", "installation_time": datetime(2023,7,15,8,0,0)},
        {"branch_id": ids["Trường Sơn"], "meter_name": "Đồng hồ Trường Sơn 01", "installation_time": datetime(2023,8,20,8,0,0)},
    ]
    for m in meters:
        upsert("meters", {"branch_id": m["branch_id"], "meter_name": m["meter_name"]}, m)

    return company_id, ids

def seed_users(company_id, branch_ids: Dict[str, Any]):
    role = {r["role_name"]: r["_id"] for r in db.roles.find({}, {"role_name": 1})}

    users = [
        {"username": "admin",          "password": hash_password("Admin@123"), "role_id": role["admin"], "branch_id": None},
        {"username": "tongcongty",     "password": hash_password("Company@123"), "role_id": role["company_manager"], "company_id": company_id, "branch_id": None},
        {"username": "van_dau_mgr",    "password": hash_password("Branch@123"), "role_id": role["branch_manager"], "branch_id": branch_ids["Văn Đẩu"]},
        {"username": "bac_son_mgr",    "password": hash_password("Branch@123"), "role_id": role["branch_manager"], "branch_id": branch_ids["Bắc Sơn"]},
        {"username": "truong_son_mgr", "password": hash_password("Branch@123"), "role_id": role["branch_manager"], "branch_id": branch_ids["Trường Sơn"]},
    ]

    for u in users:
        upsert("users", {"username": u["username"]}, {**u, "is_active": True, "last_login": None})

# --- Authorization helpers (simple demo logic) ---
def role_permissions(role_id) -> Set[str]:
    perms = db.role_permissions.find({"role_id": role_id}, {"perm_key": 1, "_id": 0})
    return {p["perm_key"] for p in perms}

def can(user: Dict[str, Any], perm_key: str) -> bool:
    rperms = role_permissions(user["role_id"])
    return perm_key in rperms

def create_branch(actor_username: str, company_id, name: str, address: str):
    user = db.users.find_one({"username": actor_username})
    if not user or not can(user, "branch:create"):
        raise PermissionError("Bạn không có quyền tạo chi nhánh")
    # Scope: company_manager can only within their company (saved on user as company_id)
    if user.get("company_id") and user["company_id"] != company_id:
        raise PermissionError("Không được tạo chi nhánh ngoài phạm vi công ty")
    doc = {"company_id": company_id, "name": name, "address": address}
    upsert("branches", {"company_id": company_id, "name": name}, doc)
    return True

def create_meter(actor_username: str, branch_id, meter_name: str, installation_time: Optional[datetime] = None):
    user = db.users.find_one({"username": actor_username})
    if not user or not can(user, "meter:create"):
        raise PermissionError("Bạn không có quyền tạo đồng hồ")
    # Scope: branch_manager can only within their branch
    if user.get("branch_id") and user["branch_id"] != branch_id:
        raise PermissionError("Không được tạo đồng hồ ngoài phạm vi chi nhánh")
    doc = {"branch_id": branch_id, "meter_name": meter_name, "installation_time": installation_time or datetime.utcnow()}
    upsert("meters", {"branch_id": branch_id, "meter_name": meter_name}, doc)
    return True

def main():
    print(f"Connecting to {MONGO_URI}, DB={MONGO_DB}")
    reset_collections()
    seed_permissions_roles()
    company_id, branch_ids = seed_org()
    seed_users(company_id, branch_ids)

    # --- Demo actions ---
    # 1) company_manager creates a new branch (OK)
    try:
        create_branch("tongcongty", company_id, "An Dương", "Hải Phòng - An Dương")
        print("[OK] company_manager tạo chi nhánh 'An Dương'")
    except Exception as e:
        print("[FAIL] company_manager create branch:", e)

    # 2) branch_manager tries to create a branch (DENIED)
    try:
        create_branch("van_dau_mgr", company_id, "Lê Chân", "Hải Phòng - Lê Chân")
        print("[UNEXPECTED] branch_manager created a branch")
    except Exception as e:
        print("[OK] branch_manager bị chặn tạo chi nhánh:", e)

    # 3) branch_manager creates a meter in their branch (OK)
    try:
        create_meter("van_dau_mgr", branch_ids["Văn Đẩu"], "Đồng hồ Văn Đẩu 03")
        print("[OK] branch_manager tạo đồng hồ thuộc Văn Đẩu")
    except Exception as e:
        print("[FAIL] branch_manager create meter:", e)

    # 4) branch_manager creates a meter in another branch (DENIED)
    try:
        create_meter("van_dau_mgr", branch_ids["Bắc Sơn"], "Đồng hồ Bắc Sơn 02")
        print("[UNEXPECTED] branch_manager created a meter in another branch")
    except Exception as e:
        print("[OK] branch_manager bị chặn tạo đồng hồ khác chi nhánh:", e)

    print("Seeding completed.")

if __name__ == "__main__":
    main()

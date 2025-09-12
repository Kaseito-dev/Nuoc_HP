import os
import random
from datetime import datetime, timezone, timedelta, time
import bcrypt as bc
from pymongo import MongoClient, ASCENDING, DESCENDING, ReturnDocument
from typing import Optional, Dict, Any, List, Set

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB  = os.getenv("MONGO_DB", "Nuoc_HP")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# -----------------------
# Helpers
# -----------------------
def hash_password(plain: str) -> str:
    return bc.hashpw(plain.encode("utf-8"), bc.gensalt()).decode("utf-8")

def upsert(collection: str, query: Dict[str, Any], doc: Dict[str, Any]):
    return db[collection].find_one_and_update(
        query, {"$setOnInsert": doc}, upsert=True, return_document=ReturnDocument.AFTER
    )

def reset_collections():
    print("Resetting collections...")
    for col in [
        "companies","branches","meters",
        "users","roles","permissions","role_permissions",
        "user_meters",
        "meter_manual_thresholds","meter_consumptions","meter_repairs","meter_measurements",
        "ai_models","predictions","alerts"
    ]:
        db[col].drop()

    # Xóa toàn bộ index (trừ _id_)
    for col_name in db.list_collection_names():
        for idx_name in list(db[col_name].index_information().keys()):
            if idx_name != "_id_":
                db[col_name].drop_index(idx_name)

# --- index helper (idempotent) ---
def _norm_keys(keys):
    return tuple((k, int(v)) for k, v in keys)

def ensure_index(coll, keys, name: str, **opts):
    info = coll.index_information()
    if name in info:
        if _norm_keys(info[name]["key"]) != _norm_keys(keys):
            coll.drop_index(name)
            return coll.create_index(keys, name=name, **opts)
        return name
    return coll.create_index(keys, name=name, **opts)

def init_indexes(db):
    # Users / Roles / Permissions / Role-Permissions
    ensure_index(db.users,       [("username", ASCENDING)],    unique=True,  name="uniq_user_username")
    ensure_index(db.roles,       [("role_name", ASCENDING)],   unique=True,  name="uniq_role_name")
    ensure_index(db.permissions, [("description", ASCENDING)], unique=True,  name="uniq_perm_desc")

    ensure_index(db.role_permissions, [("role_id", ASCENDING)],       name="idx_rp_role")
    ensure_index(db.role_permissions, [("permission_id", ASCENDING)], name="idx_rp_perm")
    ensure_index(db.role_permissions,
                 [("role_id", ASCENDING), ("permission_id", ASCENDING)],
                 unique=True, name="uniq_rp_role_perm")

    # Company–Branch–Meter
    ensure_index(db.companies, [("name", ASCENDING)], unique=True, name="uniq_company_name")
    ensure_index(db.branches,  [("company_id", ASCENDING)],        name="idx_branch_company")
    ensure_index(db.branches,  [("name", ASCENDING)],              name="idx_branch_name")
    ensure_index(db.meters,    [("branch_id", ASCENDING)],         name="idx_meter_branch")
    ensure_index(db.meters,    [("meter_name", ASCENDING)],        name="idx_meter_name")

    # User–Meter (n–n)
    ensure_index(db.user_meters, [("user_id", ASCENDING)],  name="idx_um_user")
    ensure_index(db.user_meters, [("meter_id", ASCENDING)], name="idx_um_meter")
    ensure_index(db.user_meters,
                 [("user_id", ASCENDING), ("meter_id", ASCENDING)],
                 unique=True, name="uniq_um")

    # Meter data
    ensure_index(db.meter_manual_thresholds,
                 [("meter_id", ASCENDING), ("set_time", DESCENDING)],
                 name="idx_thresh_meter_time")
    ensure_index(db.meter_consumptions,
                 [("meter_id", ASCENDING), ("recording_date", DESCENDING)],
                 name="idx_consume_meter_month")
    ensure_index(db.meter_repairs,
                 [("meter_id", ASCENDING), ("repair_time", DESCENDING)],
                 name="idx_repair_meter_time")
    ensure_index(db.meter_measurements,
                 [("meter_id", ASCENDING), ("measurement_time", DESCENDING)],
                 name="idx_meas_meter_time")

    # AI & Prediction & Alert
    ensure_index(db.ai_models,   [("name", ASCENDING)],                    unique=True, name="uniq_model_name")
    ensure_index(db.predictions, [("meter_id", ASCENDING), ("prediction_time", DESCENDING)],
                 name="idx_pred_meter_time")
    ensure_index(db.predictions, [("model_id", ASCENDING)],                name="idx_pred_model")
    ensure_index(db.alerts,      [("p_id", ASCENDING)],                    unique=True, name="uniq_alert_prediction")
    ensure_index(db.alerts,      [("time", DESCENDING)],                   name="idx_alert_time")

# -----------------------
# PERMISSIONS & ROLES
# -----------------------
def seed_permissions_roles():
    perms = [
        {"key": "branch:read",   "description": "Xem chi nhánh"},
        {"key": "branch:create", "description": "Tạo chi nhánh"},
        {"key": "branch:update", "description": "Sửa chi nhánh"},
        {"key": "branch:delete", "description": "Xóa chi nhánh"},
        {"key": "meter:read",    "description": "Xem đồng hồ"},
        {"key": "meter:create",  "description": "Tạo đồng hồ"},
        {"key": "meter:update",  "description": "Sửa đồng hồ"},
        {"key": "meter:delete",  "description": "Xóa đồng hồ"},
        {"key": "user:read",     "description": "Xem người dùng"},
        {"key": "user:create",   "description": "Tạo người dùng"},
        {"key": "user:update",   "description": "Sửa người dùng"},
        {"key": "user:delete",   "description": "Xóa người dùng"},
        {"key": "log:read",      "description": "Xem nhật ký hệ thống"},
        {"key": "log:create",    "description": "Tạo nhật ký hệ thống"},
        {"key": "log:delete",    "description": "Xóa nhật ký hệ thống"},
    ]
    for p in perms:
        upsert("permissions", {"key": p["key"]}, p)

    roles = [
        {"role_name": "admin"},
        {"role_name": "company_manager"},
        {"role_name": "branch_manager"},
    ]
    for r in roles:
        upsert("roles", {"role_name": r["role_name"]}, r)

    perm_docs = {p["key"]: p for p in db.permissions.find({}, {"_id": 1, "key": 1})}
    role_docs = {r["role_name"]: r for r in db.roles.find({}, {"_id": 1, "role_name": 1})}

    def bind(role_name: str, perm_keys: List[str]):
        missing = [k for k in perm_keys if k not in perm_docs]
        if missing:
            raise KeyError(f"Permission keys not found: {missing}")
        role_id = role_docs[role_name]["_id"]
        db.role_permissions.delete_many({"role_id": role_id})
        rp_docs = [{"role_id": role_id, "perm_key": k, "permission_id": perm_docs[k]["_id"]} for k in perm_keys]
        if rp_docs:
            db.role_permissions.insert_many(rp_docs)

    bind("admin", list(perm_docs.keys()))
    bind("company_manager", ["branch:read", "user:read", "meter:read"])
    bind("branch_manager",  ["user:read", "meter:read"])

# -----------------------
# ORG & USERS
# -----------------------
def seed_org():
    comp = upsert("companies", {"name": "Công ty Cấp Nước Hải Phòng"},
                  {"name": "Công ty Cấp Nước Hải Phòng", "address": "Hải Phòng"})
    company_id = comp["_id"]

    branches = [
        {"company_id": company_id, "name": "Văn Đẩu",    "address": "Hải Phòng - Văn Đẩu"},
        {"company_id": company_id, "name": "Bắc Sơn",    "address": "Hải Phòng - Bắc Sơn"},
        {"company_id": company_id, "name": "Trường Sơn", "address": "Hải Phòng - Trường Sơn"},
    ]
    ids = {}
    for b in branches:
        doc = upsert("branches", {"company_id": b["company_id"], "name": b["name"]}, b)
        ids[b["name"]] = doc["_id"]

    meters = [
        {"branch_id": ids["Văn Đẩu"],    "meter_name": "Đồng hồ Văn Đẩu 01",    "installation_time": datetime(2023,5,10,8,0,0)},
        {"branch_id": ids["Văn Đẩu"],    "meter_name": "Đồng hồ Văn Đẩu 02",    "installation_time": datetime(2023,6,12,8,0,0)},
        {"branch_id": ids["Bắc Sơn"],    "meter_name": "Đồng hồ Bắc Sơn 01",    "installation_time": datetime(2023,7,15,8,0,0)},
        {"branch_id": ids["Trường Sơn"], "meter_name": "Đồng hồ Trường Sơn 01", "installation_time": datetime(2023,8,20,8,0,0)},
    ]
    for m in meters:
        upsert("meters", {"branch_id": m["branch_id"], "meter_name": m["meter_name"]}, m)

    return company_id, ids

def seed_users(company_id, branch_ids: Dict[str, Any]):
    role = {r["role_name"]: r["_id"] for r in db.roles.find({}, {"role_name": 1})}
    users = [
        {"username": "admin",          "password": hash_password("Admin@123"),   "role_id": role["admin"],            "branch_id": None},
        {"username": "tongcongty",     "password": hash_password("Company@123"), "role_id": role["company_manager"],  "company_id": company_id, "branch_id": None},
        {"username": "van_dau_mgr",    "password": hash_password("Branch@123"),  "role_id": role["branch_manager"],   "branch_id": branch_ids["Văn Đẩu"]},
        {"username": "bac_son_mgr",    "password": hash_password("Branch@123"),  "role_id": role["branch_manager"],   "branch_id": branch_ids["Bắc Sơn"]},
        {"username": "truong_son_mgr", "password": hash_password("Branch@123"),  "role_id": role["branch_manager"],   "branch_id": branch_ids["Trường Sơn"]},
    ]
    for u in users:
        upsert("users", {"username": u["username"]}, {**u, "is_active": True, "last_login": None})

# -----------------------
# DOMAIN SEED
# -----------------------
def seed_meter_measurements():
    print("Seeding meter_measurements ...")
    meters = list(db.meters.find({}, {"_id": 1}))
    docs = []
    now = datetime.now(timezone.utc)
    for m in meters:
        # 10 ngày gần đây, mỗi ngày 1–2 điểm đo
        for i in range(10):
            day = (now - timedelta(days=10 - i)).date()
            for hour in random.sample([0, 5, 8, 12, 16, 20], k=random.choice([1, 2])):
                ts = datetime.combine(day, time(hour, 0, 0, tzinfo=timezone.utc))
                docs.append({
                    "meter_id": m["_id"],
                    "measurement_time": ts,
                    "instant_flow": round(random.uniform(1.8, 3.5), 3),
                    "instant_pressure": round(random.uniform(1.60, 1.95), 3),
                })
    if docs:
        db.meter_measurements.insert_many(docs)

def seed_meter_repairs():
    print("Seeding meter_repairs ...")
    meters = list(db.meters.find({}, {"_id": 1}))
    reasons = ["sensor_error", "leak_fix", "pipe_crack", "calibration"]
    locations = ["pit_A1", "street_12", "junction_B3", "station_C"]
    types = ["temporary", "full"]

    docs = []
    base = datetime.now(timezone.utc) - timedelta(days=180)
    for m in meters:
        for _ in range(random.choice([1, 1, 2])):  # 1-2 ticket/đồng hồ
            recorded = base + timedelta(days=random.randint(0, 150), hours=random.randint(0, 23))
            repair   = recorded + timedelta(hours=random.randint(1, 48))
            docs.append({
                "meter_id": m["_id"],
                "recorded_time": recorded,
                "repair_time": repair,
                "leak_reason": random.choice(reasons),
                "replacement_location": random.choice(locations),
                "replacement_type": random.choice(types),
            })
    if docs:
        db.meter_repairs.insert_many(docs)

def seed_predictions():
    print("Seeding predictions ...")
    meters = list(db.meters.find({}, {"_id": 1}))
    labels = ["normal", "leak", "anomaly_low_pressure", "anomaly_high_flow"]

    # đảm bảo có model
    model = upsert("ai_models", {"name": "demo_model_v1"}, {"name": "demo_model_v1"})
    model_id = model["_id"]

    docs = []
    base = datetime.now(timezone.utc) - timedelta(days=14)
    for m in meters:
        # mỗi đồng hồ: 7 bản ghi (2 ngày 1 bản ghi)
        for i in range(7):
            ts = base + timedelta(days=i*2, hours=random.choice([6, 13, 21]))
            flow = round(random.uniform(2.0, 3.2), 2)
            label = random.choices(labels, weights=[0.7, 0.15, 0.1, 0.05], k=1)[0]
            docs.append({
                "meter_id": m["_id"],
                "model_id": model_id,
                "prediction_time": ts,
                "predicted_threshold": round(random.uniform(1.8, 2.2), 2),
                "predicted_label": label,
                "confidence": round(random.uniform(0.6, 0.95), 2),
                "recorded_instant_flow": flow
            })
    if docs:
        db.predictions.insert_many(docs)

# -----------------------
# READ / WRITE demo
# -----------------------
def role_permissions(role_id) -> Set[str]:
    perms = db.role_permissions.find({"role_id": role_id}, {"perm_key": 1, "_id": 0})
    return {p["perm_key"] for p in perms}

def can(user: Dict[str, Any], perm_key: str) -> bool:
    rperms = role_permissions(user["role_id"])
    return perm_key in rperms

def list_branches(actor_username: str) -> List[Dict[str, Any]]:
    user = db.users.find_one({"username": actor_username})
    if not user or not can(user, "branch:read"):
        raise PermissionError("Bạn không có quyền xem chi nhánh")
    return list(db.branches.find({}, {"_id": 0, "name": 1, "address": 1}))

def list_meters(actor_username: str) -> List[Dict[str, Any]]:
    user = db.users.find_one({"username": actor_username})
    if not user or not can(user, "meter:read"):
        raise PermissionError("Bạn không có quyền xem đồng hồ")
    cur = db.meters.find({}, {"_id": 0, "branch_id": 1, "meter_name": 1, "installation_time": 1})
    return list(cur)

def create_branch(actor_username: str, company_id, name: str, address: str):
    user = db.users.find_one({"username": actor_username})
    if not user or not can(user, "branch:create"):
        raise PermissionError("Bạn không có quyền tạo chi nhánh")
    doc = {"company_id": company_id, "name": name, "address": address}
    upsert("branches", {"company_id": company_id, "name": name}, doc)
    return True

def create_meter(actor_username: str, branch_id, meter_name: str, installation_time: Optional[datetime] = None):
    user = db.users.find_one({"username": actor_username})
    if not user or not can(user, "meter:create"):
        raise PermissionError("Bạn không có quyền tạo đồng hồ")
    doc = {
        "branch_id": branch_id,
        "meter_name": meter_name,
        "installation_time": installation_time or datetime.utcnow()
    }
    upsert("meters", {"branch_id": branch_id, "meter_name": meter_name}, doc)
    return True

def update_meter(actor_username: str, branch_id, meter_name: str, new_name: Optional[str] = None):
    user = db.users.find_one({"username": actor_username})
    if not user or not can(user, "meter:update"):
        raise PermissionError("Bạn không có quyền sửa đồng hồ")
    if not new_name:
        raise ValueError("new_name is required")
    res = db.meters.update_one(
        {"branch_id": branch_id, "meter_name": meter_name},
        {"$set": {"meter_name": new_name}}
    )
    return res.modified_count > 0

def delete_meter(actor_username: str, branch_id, meter_name: str):
    user = db.users.find_one({"username": actor_username})
    if not user or not can(user, "meter:delete"):
        raise PermissionError("Bạn không có quyền xóa đồng hồ")
    res = db.meters.delete_one({"branch_id": branch_id, "meter_name": meter_name})
    return res.deleted_count > 0

# -----------------------
# main
# -----------------------
def main():
    print(f"Connecting to {MONGO_URI}, DB={MONGO_DB}")
    reset_collections()
    seed_permissions_roles()
    company_id, branch_ids = seed_org()
    seed_users(company_id, branch_ids)

    # Tạo index (có thể đặt trước hoặc sau domain seed; để sau cũng ổn)
    init_indexes(db)

    # Seed domain data (tham chiếu meter_id hiện tại)
    seed_meter_measurements()
    seed_meter_repairs()
    seed_predictions()

    # --- Demo hành vi theo yêu cầu ---
    print("\n[READ] company_manager có thể xem:")
    try:
        print("Branches:", list_branches("tongcongty")[:2])
        print("Meters:", list_meters("tongcongty")[:2])
    except Exception as e:
        print("READ company_manager error:", e)

    print("\n[READ] branch_manager có thể xem:")
    try:
        print("Branches:", list_branches("van_dau_mgr")[:2])
        print("Meters:", list_meters("van_dau_mgr")[:2])
    except Exception as e:
        print("READ branch_manager error:", e)

    print("\n[WRITE] company_manager tạo chi nhánh (PHẢI BỊ CHẶN):")
    try:
        create_branch("tongcongty", company_id, "An Dương", "Hải Phòng - An Dương")
        print("[UNEXPECTED] company_manager vẫn tạo được (sai)")
    except Exception as e:
        print("[OK] bị chặn:", e)

    print("\n[WRITE] branch_manager tạo đồng hồ (PHẢI BỊ CHẶN):")
    try:
        create_meter("van_dau_mgr", branch_ids["Văn Đẩu"], "Đồng hồ Văn Đẩu 03")
        print("[UNEXPECTED] branch_manager vẫn tạo được (sai)")
    except Exception as e:
        print("[OK] bị chặn:", e)

    print("\n[WRITE] admin tạo / sửa / xóa (ĐƯỢC PHÉP):")
    try:
        ok1 = create_meter("admin", branch_ids["Văn Đẩu"], "Đồng hồ Văn Đẩu 03")
        ok2 = update_meter("admin", branch_ids["Văn Đẩu"], "Đồng hồ Văn Đẩu 03", new_name="Đồng hồ Văn Đẩu 03 - NEW")
        ok3 = delete_meter("admin", branch_ids["Văn Đẩu"], "Đồng hồ Văn Đẩu 03 - NEW")
        print(f"[OK] admin: create={ok1}, update={ok2}, delete={ok3}")
    except Exception as e:
        print("[FAIL] admin write:", e)

    print("\nSeeding completed.")

if __name__ == "__main__":
    main()

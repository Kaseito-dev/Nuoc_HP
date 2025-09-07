from pymongo import MongoClient, ASCENDING, DESCENDING
from flask import current_app, g
from flask_jwt_extended import JWTManager

jwt = JWTManager()

def get_db():
    if "mongo_client" not in g:
        uri = current_app.config["MONGO_URI"]
        g.mongo_client = MongoClient(uri)
    client = g.mongo_client
    dbname = current_app.config["MONGO_DB"]
    return client[dbname]


def init_indexes(db):
    # Users & AuthZ
   
    db.users.create_index([("username", ASCENDING)], unique=True, name="uniq_user_username")
    db.roles.create_index([("role_name", ASCENDING)], unique=True, name="uniq_role_name")
    db.permissions.create_index([("description", ASCENDING)], unique=True, name="uniq_perm_desc")
    db.role_permissions.create_index([("role_id", ASCENDING)], name="idx_rp_role")
    db.role_permissions.create_index([("permission_id", ASCENDING)], name="idx_rp_perm")

    # Company–Branch–Meter
    db.companies.create_index([("name", ASCENDING)], unique=True, name="uniq_company_name")
    db.branches.create_index([("company_id", ASCENDING)], name="idx_branch_company")
    db.branches.create_index([("name", ASCENDING)], name="idx_branch_name")
    db.meters.create_index([("branch_id", ASCENDING)], name="idx_meter_branch")
    db.meters.create_index([("meter_name", ASCENDING)], name="idx_meter_name")

    # User–Meter (n–n)
    db.user_meters.create_index([("user_id", ASCENDING)], name="idx_um_user")
    db.user_meters.create_index([("meter_id", ASCENDING)], name="idx_um_meter")
    db.user_meters.create_index(
        [("user_id", ASCENDING), ("meter_id", ASCENDING)],
        unique=True,
        name="uniq_um" 
    )

    # Meter data
    db.meter_manual_thresholds.create_index([("meter_id", ASCENDING), ("set_time", DESCENDING)], name="idx_thresh_meter_time")
    db.meter_consumptions.create_index([("meter_id", ASCENDING), ("recording_date", DESCENDING)], name="idx_consume_meter_month")
    db.meter_repairs.create_index([("meter_id", ASCENDING), ("repair_time", DESCENDING)], name="idx_repair_meter_time")
    db.meter_measurements.create_index([("meter_id", ASCENDING), ("measurement_time", DESCENDING)], name="idx_meas_meter_time")

    # AI & Prediction & Alert
    db.ai_models.create_index([("name", ASCENDING)], unique=True, name="uniq_model_name")
    db.predictions.create_index([("meter_id", ASCENDING), ("prediction_time", DESCENDING)], name="idx_pred_meter_time")
    db.predictions.create_index([("model_id", ASCENDING)], name="idx_pred_model")
    db.alerts.create_index([("p_id", ASCENDING)], unique=True, name="uniq_alert_prediction")  # 1-1
    db.alerts.create_index([("time", DESCENDING)], name="idx_alert_time")

    db.roles.create_index([("role_name", ASCENDING)], unique=True, name="uniq_role_name")
    db.permissions.create_index([("description", ASCENDING)], unique=True, name="uniq_perm_desc")
    db.role_permissions.create_index([("role_id", ASCENDING)], name="idx_rp_role")
    db.role_permissions.create_index([("permission_id", ASCENDING)], name="idx_rp_perm")
    db.role_permissions.create_index([("role_id", ASCENDING), ("permission_id", ASCENDING)],
                                     unique=True, name="uniq_rp_role_perm")


def close_db(e=None):
    client = g.pop("mongo_client", None)
    if client:
        client.close()

def init_jwt_blocklist_indexes(db):
    # Lưu token bị logout vào collection jwt_blocklist
    # TTL tự xoá khi hết hạn
    db.jwt_blocklist.create_index([("jti", ASCENDING)], unique=True, name="uniq_jti")
    db.jwt_blocklist.create_index("exp", expireAfterSeconds=0, name="ttl_exp")  # xoá sau khi exp <= now

from ...extensions import get_db
from ...utils.bson import to_object_id, oid_str

def list_meters_of_user(user_id: str):
    db = get_db()
    cur = db.user_meters.find({"user_id": to_object_id(user_id)})
    out = []
    for link in cur:
        # ghép thêm thông tin meter nếu cần
        m = db.meters.find_one({"_id": link["meter_id"]})
        if m:
            m["id"] = oid_str(m.pop("_id"))
            out.append(m)
    return out

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from ..authz.require import require_permissions, require_password_confirmation
from .schemas import MeterCreate, MeterUpdate, MeterOut
from .service import create_meter_admin_only, get_meter, list_meters, update_meter, remove_meter, get_meters_list, build_leak_overview
from ..common.response import json_ok, created, no_content
from ..common.pagination import parse_pagination, build_links
from werkzeug.exceptions import BadRequest
from typing import Optional, Dict, Any, List, Tuple
import traceback
from ...errors import BadRequest
from datetime import datetime
from...utils.time_utils import day_bounds_utc

bp = Blueprint("meters", __name__, url_prefix="meters")

@bp.post("/")
@jwt_required()
@require_password_confirmation()
@require_permissions("meter:create")
def create():
    print("Creating meter...")
    try:
        current_user = get_jwt()
        print("Current user claims:", current_user)
        data = MeterCreate(**(request.get_json(silent=True) or {}))
        print("Parsed data:", data)
    except Exception as e:
        traceback.print_exc()
        raise BadRequest(f"Invalid request: {e}")
    m = create_meter_admin_only(data)
    return created(f"/api/v1/meters/{m.id}", m.model_dump())


@bp.get("/")
@jwt_required()
@require_permissions(["meter:read"])
def list_():
    page, page_size = parse_pagination(request.args)
    q = request.args.get("q")
    sort = request.args.get("sort")
    items, has_next = list_meters(page, page_size, q, sort)
    body = {"items": [MeterOut(**x).model_dump() for x in items], "page": page, "page_size": page_size}
    links = build_links("/api/v1/meters", page, page_size, has_next, {"q": q or "", "sort": sort or ""})
    return json_ok(body, headers={"Link": links})



@bp.patch("/<string:mid>")
@jwt_required()
@require_password_confirmation()
@require_permissions("meter:update")
def update(mid):
    print(f"Updating meter {mid}...")
    try:
        data = MeterUpdate(**(request.get_json(silent=True) or {}))
    except Exception as e:
        raise BadRequest(str(e))
    print("Parsed update data:", data)
    m = update_meter(mid, data)
    return json_ok(MeterOut(**m).model_dump()) if m else json_ok({"error":{"code":"NOT_FOUND","message":"Not found"}}, 404)

@bp.delete("/<string:mid>")
@jwt_required()
@require_password_confirmation()
@require_permissions("meter:delete")
def remove(mid):
    ok = remove_meter(mid)
    return (
    (jsonify({"status": "ok"}), 200)
    if ok
    else (jsonify({"error": {"code": "NOT_FOUND", "message": "Not found"}}), 404)
)

@bp.get("/with_status/")
@jwt_required()
@require_permissions("branch:read")
def list_meters():
    date_str = request.args.get("date")   # ví dụ: /with_status/?date=2025-09-12
    items = get_meters_list(date_str)
    return jsonify({"items": items}), 200

@bp.get("/count/leak-overview")
@jwt_required()
@require_permissions("meter:read")
def leak_overview():
    """
    Tổng toàn hệ thống :
      - total_meters
      - leak_meters (distinct theo meter_id trong ngày)
      - normal_meters
    Query: ?date=YYYY-MM-DD (mặc định: hôm nay theo Asia/Ho_Chi_Minh)
    """
    try:
        date_q = request.args.get("date")
        date_str, start_utc, end_utc = day_bounds_utc(date_q)

        result = build_leak_overview(start_utc, end_utc)
        return jsonify({"success": True, "date": date_str, **result}), 200

    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}), 400
    except Exception:
        return jsonify({"success": False, "error": "Internal server error"}), 500



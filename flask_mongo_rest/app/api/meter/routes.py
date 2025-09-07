from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required
from ..authz.require import require_permissions
from .schemas import MeterCreate, MeterUpdate, MeterOut
from .service import create_meter, get_meter, list_meters, update_meter, remove_meter
from ...errors import BadRequest
from ..common.response import json_ok, created, no_content
from ..common.pagination import parse_pagination, build_links
import traceback
bp = Blueprint("meters", __name__)

@bp.post("/")
@jwt_required()
@require_permissions("meter:create")
def create():
    print("Creating meter...")
    try:
        current_user = get_jwt()
        print("Current user claims:", current_user)
        data = MeterCreate(**(request.get_json(silent=True) or {}))
    except Exception as e:
        traceback.print_exc()
        raise BadRequest(f"Invalid request: {e}")
    m = create_meter(data)
    return created(f"/api/v1/meters/{m['id']}", MeterOut(**m).model_dump())


@bp.get("/")
@jwt_required()
@require_permissions(['meter:update', 'meter:delete', 'meter:create'])
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
@require_permissions("meter:create")
def update(mid):
    try:
        data = MeterUpdate(**(request.get_json(silent=True) or {}))
    except Exception as e:
        raise BadRequest(str(e))
    m = update_meter(mid, data)
    return json_ok(MeterOut(**m).model_dump()) if m else json_ok({"error":{"code":"NOT_FOUND","message":"Not found"}}, 404)

@bp.delete("/<string:mid>")
@jwt_required()
@require_permissions("meter:delete")
def remove(mid):
    ok = remove_meter(mid)
    return no_content() if ok else json_ok({"error":{"code":"NOT_FOUND","message":"Not found"}}, 404)

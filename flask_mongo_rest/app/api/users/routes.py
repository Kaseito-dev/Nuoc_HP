
import traceback
from flask import Blueprint, request
from .schemas import UserCreate, UserUpdate, UserOut
from ...errors import BadRequest
from ..common.response import json_ok, created, no_content
from ..common.pagination import parse_pagination, build_links
from flask_jwt_extended import jwt_required
from ..authz.require import *
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from pydantic import ValidationError
from .schemas import UserCreate
from .service import *

bp = Blueprint("users", __name__)

@bp.post("/")
@jwt_required()
@require_password_confirmation()
@require_role("admin")
def create_user():
    try:
        payload = UserCreate(**request.get_json(force=True))
    except ValidationError as e:
        return jsonify({"error": "ValidationError", "details": e.errors()}), 422

    user = create_user_admin_only(payload)
    return jsonify(user.model_dump()), 201

@bp.get("/")
@jwt_required()
@require_role(["admin", "company_manager"])
def list_():
    page, page_size = parse_pagination(request.args)
    q = request.args.get("q")
    sort = request.args.get("sort")
    items, has_next = list_user(page, page_size, q, sort)
    body = {
        "items": [UserOut(**u).model_dump() for u in items],
        "page": page,
        "page_size": page_size
    }
    links = build_links("/api/v1/users", page, page_size, has_next, extra_params={"q": q or "", "sort": sort or ""})
    return json_ok(body, headers={"Link": links})

@bp.get("/<string:uid>")
@jwt_required()
@require_role(["admin", "company_manager", "branch_manager"])
def detail(uid):
    user = get_user(uid)
    if not user:
        return json_ok({"error": {"code": "NOT_FOUND", "message": "Not found"}}, 404)
    return json_ok(UserOut(**user).model_dump())


@bp.patch("/<string:uid>")
@jwt_required()
@require_password_confirmation()
@require_role("admin")
def update_user(uid):
    try:
        payload = UserUpdate(**request.get_json(force=True))
    except ValidationError as e:
        print(traceback.format_exc())
        return jsonify({"error": "ValidationError", "details": e.errors()}), 422

    user = update_user_admin_only(uid, payload)
    return jsonify(user.model_dump()), 200

@bp.delete("/<string:uid>")
@jwt_required()
@require_password_confirmation()
@require_role("admin")
def remove(uid):
    ok = remove_user(uid)
    return (
        (jsonify({"status": "ok"}), 200)
        if ok
        else (jsonify({"error": {"code": "NOT_FOUND", "message": "Not found"}}), 404)
    )

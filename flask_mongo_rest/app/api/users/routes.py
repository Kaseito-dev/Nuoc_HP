
from flask import Blueprint, request
from .schemas import UserCreate, UserUpdate, UserOut
from .service import  get_user, list_user, update_user_info, remove_user
from ...errors import BadRequest
from ..common.response import json_ok, created, no_content
from ..common.pagination import parse_pagination, build_links
from flask_jwt_extended import jwt_required
from ..authz.require import require_permissions


bp = Blueprint("users", __name__)

# @bp.post("/")
# @jwt_required()
# @require_permissions("user.write")
# def create():
#     payload = request.get_json(silent=True) or {}
#     try:
#         data = UserCreate(**payload)
#     except Exception as e:
#         raise BadRequest(str(e))
#     user = create_user(data)
#     location = f"/api/v1/users/{user['id']}"
#     return created(location, UserOut(**user).model_dump())

@bp.get("/")
@jwt_required()
@require_permissions("user.read")
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
@require_permissions("user.read")
def detail(uid):
    user = get_user(uid)
    if not user:
        return json_ok({"error": {"code": "NOT_FOUND", "message": "Not found"}}, 404)
    return json_ok(UserOut(**user).model_dump())

@bp.patch("/<string:uid>")
@jwt_required()
@require_permissions("user.write")
def update(uid):
    payload = request.get_json(silent=True) or {}
    try:
        data = UserUpdate(**payload)
    except Exception as e:
        raise BadRequest(str(e))
    user = update_user_info(uid, data)
    if not user:
        return json_ok({"error": {"code": "NOT_FOUND", "message": "Not found"}}, 404)
    return json_ok(UserOut(**user).model_dump())

@bp.delete("/<string:uid>")
@jwt_required()
@require_permissions("user.write")
def remove(uid):
    ok = remove_user(uid)
    return no_content() if ok else json_ok({"error": {"code": "NOT_FOUND", "message": "Not found"}}, 404)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from .schemas import  LoginIn, UserPublic
from .service import  validate_login
from ...errors import BadRequest
from ..common.response import json_ok
from ...extensions import get_db
from bson import ObjectId
import bcrypt as bc
from ...extensions import TOKEN_BLOCKLIST
import traceback

bp = Blueprint("auth", __name__, url_prefix="auth")

@bp.post("/login")
def login():
    try:
        data = LoginIn(**(request.get_json(silent=True) or {}))
    except Exception as e:
        raise BadRequest(str(e))

    try:
        u = validate_login(data)

        # Thêm scope vào claims
        claims = {
            "username": u["username"],
            "role_id": u["role_id"],
            "role_name": u.get("role_name"),
            "company_id": u["company_id"],
            "branch_id": u["branch_id"],
            "permissions": list(u.get("permissions", []))
        }

        access  = create_access_token(identity=u["id"], additional_claims=claims)
        refresh = create_refresh_token(identity=u["id"], additional_claims=claims)

    except Exception as e:
        traceback.print_exc()
        raise e

    return json_ok({
        "access_token": access,
        "refresh_token": refresh,
        "user": u  # trả luôn thông tin user cho FE nếu muốn
    })


@bp.post("/refresh")
@jwt_required()
def refresh():
    uid = get_jwt_identity()
    return json_ok({"access_token": create_access_token(identity=uid)})


@bp.post("/logout")
@jwt_required()
def logout():
    jti = get_jwt()["jti"]   # lấy JWT ID của token hiện tại
    TOKEN_BLOCKLIST.add(jti)
    return jsonify({"msg": "Successfully logged out"}), 200



# app/api/common/routes.py
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from .service import get_overview_scoped as get_overview
from ..authz.require import require_role

bp = Blueprint("stats", __name__, url_prefix="/stats")

@bp.get("/overview")
@jwt_required()
@require_role(["admin", "company_manager", "branch_manager"])
def overview():
    data = get_overview()
    return jsonify(data), 200

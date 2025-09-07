from flask import Blueprint
from .service import get_meters

bp = Blueprint("user_meters", __name__)

@bp.get("/<string:user_id>")
def list_for_user(user_id):
    items = get_meters(user_id)
    return {"items": items}, 200

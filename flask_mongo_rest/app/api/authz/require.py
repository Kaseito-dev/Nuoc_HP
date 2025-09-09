from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, jwt_required
from flask import request
from .repo import load_permissions_for_user
from ..auth.utils import validate_current_user_password

def _flatten_to_str_set(*items) -> set[str]:
    """Nhận tuple args có thể lẫn list/tuple/set và chuỗi, flatten 1–2 cấp,
    ép tất cả về str và trả về set[str]."""
    out = []
    stack = list(items)
    while stack:
        x = stack.pop()
        if x is None:
            continue
        if isinstance(x, (list, tuple, set)):
            stack.extend(x)
        else:
            out.append(str(x))
    return set(out)

def _normalize_perms(perms) -> set[str]:
    """Chuẩn hóa perms từ repo thành set[str]. Hỗ trợ:
    - list[str]
    - set[str]
    - list[dict] có key 'perm_key' hoặc 'key'
    - None
    """
    if perms is None:
        return set()
    if isinstance(perms, (set, list, tuple)):
        tmp = []
        for p in perms:
            if isinstance(p, dict):
                # ưu tiên 'perm_key', fallback 'key'
                val = p.get("perm_key", p.get("key"))
                if val is not None:
                    tmp.append(str(val))
            else:
                tmp.append(str(p))
        return set(tmp)
    # fallback: 1 giá trị đơn lẻ
    return {str(perms)}

def require_permissions(*required):
    """AND: yêu cầu đủ tất cả quyền. 
    Dùng được các kiểu:
      @require_permissions("meter:create")
      @require_permissions("meter:create", "meter:update")
      @require_permissions(["meter:create", "meter:update"])
    """
    required_set = _flatten_to_str_set(*required)

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            uid = get_jwt_identity()
            perms_raw = load_permissions_for_user(uid)
            perms = _normalize_perms(perms_raw)

            missing = sorted(p for p in required_set if p not in perms)
            if missing:
                return jsonify({"error": {
                    "code": "FORBIDDEN",
                    "message": "Missing permissions",
                    "details": missing
                }}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco

def require_any(*options):
    """OR: cần tối thiểu 1 quyền trong danh sách."""
    options_set = _flatten_to_str_set(*options)

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            uid = get_jwt_identity()
            perms_raw = load_permissions_for_user(uid)
            perms = _normalize_perms(perms_raw)

            if not (options_set & perms):  # giao hai tập rỗng -> thiếu quyền
                return jsonify({"error": {
                    "code": "FORBIDDEN",
                    "message": "Permission required",
                    "details": sorted(options_set)
                }}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco

def require_password_confirmation(json_key: str = "password"):
    """
    Dùng: @jwt_required() + @require_password_confirmation()
    Expect JSON body có {"password": "..."} (hoặc key tuỳ đổi)
    """
    def deco(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            plain = data.get(json_key)
            ok, resp, _ = validate_current_user_password(plain)
            if not ok:
                return resp, 401
            return fn(*args, **kwargs)
        return wrapper
    return deco
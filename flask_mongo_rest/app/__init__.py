
from flask import Flask
from .config import get_config
from .extensions import get_db, init_indexes, close_db, jwt, init_jwt_blocklist_indexes
from .api import api_v1
from .errors import register_error_handlers
from flask_cors import CORS

def create_app(env: str = "dev") -> Flask:
    print("Environment:", env)
    print("Starting app...")
    app = Flask(__name__)
    app.config.from_object(get_config(env))

    CORS(app)
    

    with app.app_context():
        db = get_db()
        init_indexes(db)
        init_jwt_blocklist_indexes(get_db())
    
    @jwt.token_in_blocklist_loader
    def _token_in_blocklist(jwt_header, jwt_payload):
        from .extensions import get_db
        jti = jwt_payload["jti"]
        return get_db().jwt_blocklist.find_one({"jti": jti}) is not None

    # Tuỳ chọn: message khi token bị revoke/expired
    @jwt.revoked_token_loader
    def _revoked(jwt_header, jwt_payload):
        return {"error": {"code": "TOKEN_REVOKED", "message": "Token has been revoked"}}, 401

    @jwt.expired_token_loader
    def _expired(jwt_header, jwt_payload):
        return {"error": {"code": "TOKEN_EXPIRED", "message": "Token has expired"}}, 401
    app.teardown_appcontext(close_db)
    app.register_blueprint(api_v1)
    register_error_handlers(app)
    jwt.init_app(app)
    return app
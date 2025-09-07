
from flask import Flask
from .config import get_config
from .extensions import get_db, init_indexes, close_db, jwt
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
    

    app.teardown_appcontext(close_db)
    app.register_blueprint(api_v1)
    register_error_handlers(app)
    jwt.init_app(app)
    return app
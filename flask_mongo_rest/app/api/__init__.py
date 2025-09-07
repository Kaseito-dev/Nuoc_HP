
from flask import Blueprint
from .users.routes import bp as users_bp
from .companies.routes import bp as companies_bp
from .user_meter.routes import bp as user_meter
from .auth.routes import bp as auth_bp
from .meter.routes import bp as meter_bp
from .branches.routes import bp as branches_bp


api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")
api_v1.register_blueprint(users_bp, url_prefix="/users")
api_v1.register_blueprint(companies_bp, url_prefix="/companies")
api_v1.register_blueprint(user_meter, url_prefix="/user-meter")
api_v1.register_blueprint(auth_bp, url_prefix="/auth")
api_v1.register_blueprint(meter_bp, url_prefix="/meters")
api_v1.register_blueprint(branches_bp, url_prefix="/branches")

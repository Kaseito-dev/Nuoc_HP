
import os

class BaseConfig:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB  = os.getenv("MONGO_DB", "Nuoc_HP")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-jwt")
    JSON_SORT_KEYS = False

class DevConfig(BaseConfig):
    DEBUG = True

class ProdConfig(BaseConfig):
    DEBUG = False

def get_config(env: str):
    return {"dev": DevConfig, "prod": ProdConfig}.get(env, DevConfig)

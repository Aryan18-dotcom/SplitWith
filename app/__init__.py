from flask import Flask
from pymongo import MongoClient
from config import Config
from pymongo.errors import ServerSelectionTimeoutError
import logging

mongo = None

def create_app(config_class=Config):
    global mongo
    app = Flask(__name__, static_folder="../static")
    app.config.from_object(config_class)
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s | %(levelname)s | %(message)s",)
    app.logger.setLevel(logging.DEBUG)

    # Initialize Mongo client
    mongo = MongoClient(
        app.config["MONGO_URI"],
        serverSelectionTimeoutMS=5000
    )

    try:
        mongo.admin.command("ping")
        print("✅ Mongo connected")
    except ServerSelectionTimeoutError as e:
        print("❌ Mongo connection failed:", e)
        raise

    app.mongo_client = mongo

    # Import blueprints here to avoid circular imports
    from .routes.userAuth import user_bp
    from .routes.otp import otp_bp
    from .routes.dashboard.homeRoute import home_bp
    from .routes.dashboard.groupRoute import group_bp
    from .routes.dashboard.expenseRoute import expense_bp
    from .routes.dashboard.settingsRoute import settings_bp
    from .routes.landing import land
    from .routes.dashboard.reportRoute import report_bp

    # Register blueprints
    app.register_blueprint(land)
    app.register_blueprint(user_bp)
    app.register_blueprint(otp_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(group_bp)
    app.register_blueprint(expense_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(report_bp)

    return app

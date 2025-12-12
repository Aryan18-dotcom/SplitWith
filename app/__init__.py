from flask import Flask
from flask_pymongo import PyMongo
from config import Config

mongo = PyMongo()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder="../static")
    app.config.from_object(config_class)

    # Initialize Mongo
    mongo.init_app(app)

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

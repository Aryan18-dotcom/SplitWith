import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")

    # MongoDB Configuration
    MONGO_URI = os.environ.get("MONGO_URI")
    MONGO_DBNAME = os.environ.get("MONGO_DBNAME")

    # Email Configuration
    SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
    SMTP_PASS = os.environ.get("SMTP_PASS")
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT"))

    # Otp Expire Timing
    OTP_TTL_SECONDS = 5 * 60

    # JWT Configuration
    JWT_SECRET = os.environ.get("JWT_SECRET")


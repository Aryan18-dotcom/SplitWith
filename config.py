import os
from dotenv import load_dotenv

load_dotenv()

def get_required_env(key):
    value = os.environ.get(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set.")
    return value

class Config:
    # Flask Configuration
    SECRET_KEY = get_required_env("FLASK_SECRET_KEY")

    # MongoDB Configuration
    MONGO_URI = get_required_env("MONGO_URI")
    MONGO_DBNAME = get_required_env("MONGO_DBNAME")

    # Email Configuration
    SMTP_EMAIL = get_required_env("SMTP_EMAIL")
    SMTP_PASS = get_required_env("SMTP_PASS")
    SMTP_HOST = get_required_env("SMTP_HOST")
    
    # The fix: Ensure the string is available before converting to int
    SMTP_PORT = int(get_required_env("SMTP_PORT"))

    # Otp Expire Timing
    OTP_TTL_SECONDS = 5 * 60

    # JWT Configuration
    JWT_SECRET = get_required_env("JWT_SECRET")
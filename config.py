import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "super-secret-key")

    # MongoDB Configuration
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Admin:bbPiPewkxTT6QfzO@firstcluster.wwqwyh2.mongodb.net/?appName=FirstCluster")
    MONGO_DBNAME = os.environ.get("MONGO_DBNAME", "MongoDB-Test")

    # Email Configuration
    SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "sthetic14@gmail.com")
    SMTP_PASS = os.environ.get("SMTP_PASS", "tmnb ptoi ygry qwnw")
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))

    # Otp Expire Timing
    OTP_TTL_SECONDS = 5 * 60

    # JWT Configuration
    JWT_SECRET = os.environ.get("JWT_SECRET", "your-very-secret-key")


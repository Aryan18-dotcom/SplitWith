from . import GetDB
from config import Config
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import random
import socket

class OTPModel:

    @staticmethod
    def collection():
        db = GetDB._get_db()
        return db.otps

    @staticmethod
    def generate_otp(email):
        otp = random.randint(100000, 999999)
        expires_at = datetime.utcnow() + timedelta(seconds=Config.OTP_TTL_SECONDS)

        OTPModel.collection().update_one(
            {"email": email},
            {"$set": {"otp": otp, "expires_at": expires_at, "verified": False}},
            upsert=True
        )

        # Send OTP via email
        # OTPModel.send_email(email, otp)

        return otp

    @staticmethod
    def send_email(to_email, otp) -> bool:
        subject = "Your OTP Code"
        body = (
            f"Your OTP code is: {otp}\n\n"
            f"It is valid for {Config.OTP_TTL_SECONDS // 60} minutes."
        )

        msg = MIMEMultipart()
        msg["From"] = Config.SMTP_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            server = smtplib.SMTP(
                Config.SMTP_HOST,
                Config.SMTP_PORT,
                timeout=15  # ✅ REQUIRED for Render
            )

            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(Config.SMTP_EMAIL, Config.SMTP_PASS)

            server.send_message(msg)
            server.quit()

            return True

        except (smtplib.SMTPException, socket.error) as e:
            print(f"❌ [EMAIL ERROR] Failed to send OTP → {to_email}")
            print(f"🧨 Reason: {e}")
            return False
        
    @staticmethod
    def verify_otp(email, otp):
        record = OTPModel.collection().find_one({"email": email})
        if not record:
            return False, "OTP not found"
        if record.get("verified"):
            return False, "OTP already verified"
        if record.get("otp") != otp:
            return False, "Incorrect OTP"
        if datetime.utcnow() > record.get("expires_at"):
            return False, "OTP expired"

        OTPModel.collection().update_one(
            {"email": email},
            {"$set": {"verified": True}}
        )
        return True, "OTP verified"

    @staticmethod
    def resend_otp(email):
        return OTPModel.generate_otp(email)

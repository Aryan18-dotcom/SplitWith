from . import GetDB
from config import Config
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import random

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
        sender_email = Config.SMTP_EMAIL
        sender_password = Config.SMTP_PASS
        smtp_host = Config.SMTP_HOST
        smtp_port = Config.SMTP_PORT

        subject = "Your OTP Code"
        body = (
            f"Your OTP code is: {otp}\n\n"
            f"It is valid for {Config.OTP_TTL_SECONDS // 60} minutes."
        )

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()

            print(f"✅ OTP sent to {to_email}")
            return True   # ✅ IMPORTANT

        except Exception as e:
            print(f"❌ Error sending OTP: {e}")
            return False  # ✅ IMPORTANT


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
    def resend_otp(email) -> bool:
        """
        Regenerate OTP and resend email
        """
        # 🔐 Generate new OTP
        otp = OTPModel.generate_otp(email)
        if not otp:
            print(f"❌ [RESEND OTP] OTP generation failed → {email}")
            return False

        # ✉️ Send OTP email
        success = OTPModel.send_email(email, otp)

        if success:
            print(f"✅ [RESEND OTP] OTP resent successfully → {email}")
            return True

        print(f"❌ [RESEND OTP] Email send failed → {email}")
        return False


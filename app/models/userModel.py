from werkzeug.security import generate_password_hash
from . import GetDB
from datetime import datetime
from bson import ObjectId

class UserModel:

    @staticmethod
    def collection():
        db = GetDB._get_db()
        return db.users  # collection name in lowercase


    @staticmethod
    def create_user(email, username, full_name, phone_no, password, extra_fields=None):

        base_user = {
            "profile_image": None,
            "email": email.lower().strip(),
            "username": username.lower().strip(),
            "full_name": full_name,
            "phone_no": phone_no,
            "password": generate_password_hash(password),
            "created_at": datetime.utcnow(),

            "isVerified": False,
            "isLogin": False,
            "lastLogin": None,
            "last_active_device": None,
            "devices": [],

            # Security defaults
            "2fa_enabled": True,
            "2fa_method": "email",
            "2fa_secret": None,
            "security_questions": [],
            "account_activity_alerts": {
                "login_from_new_device": True,
                "password_change": True,
                "profile_change": True
            },
            "password_last_changed": datetime.utcnow(),
            "failed_login_attempts": 0,
            "account_locked_until": None
        }

        # Merge custom fields
        if extra_fields:
            base_user.update(extra_fields)

        return UserModel.collection().insert_one(base_user)

    
    @staticmethod
    def update_password(user_id, new_password):
        """
        Updates the user password and stores the timestamp of the change.
        """
        hashed_password = generate_password_hash(new_password)
        return UserModel.collection().update_one(
            {"_id": user_id},
            {"$set": {"password": hashed_password, "password_last_changed": datetime.utcnow()}}
        )

    @staticmethod
    def enable_2fa(user_id, method, secret=None):
        """
        Enables 2FA for the user.
        """
        return UserModel.collection().update_one(
            {"_id": user_id},
            {"$set": {"2fa_enabled": True, "2fa_method": method, "2fa_secret": secret}}
        )

    @staticmethod
    def disable_2fa(user_id):
        """
        Disables 2FA for the user.
        """
        return UserModel.collection().update_one(
            {"_id": user_id},
            {"$set": {"2fa_enabled": False, "2fa_method": None, "2fa_secret": None}}
        )

    @staticmethod
    def set_security_questions(user_id, questions_answers):
        """
        questions_answers: list of dicts [{'question': '...', 'answer_hash': '...'}]
        """
        return UserModel.collection().update_one(
            {"_id": user_id},
            {"$set": {"security_questions": questions_answers}}
        )

    
    @staticmethod
    def find_by_email_or_username(value):
        if not value:
            return None

        value = value.lower().strip()

        return UserModel.collection().find_one({
            "$or": [
                {"email": {"$regex": f"^{value}$", "$options": "i"}},
                {"username": {"$regex": f"^{value}$", "$options": "i"}}
            ]
        })


    
    @staticmethod
    def get_user_by_ID(user_id):
        return UserModel.collection().find_one({"_id":ObjectId(user_id)})
    
    @staticmethod
    def get_all_active_users_except(exclude_user_id):
        return list(UserModel.collection().find({
            "_id": {"$ne": ObjectId(exclude_user_id)}
        }))

    @staticmethod
    def get_all_users():
        return list(UserModel.collection().find())
    
    @staticmethod
    def update_login_status(user_id, is_login):
        return UserModel.collection().update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "isLogin": is_login,
                    "lastLogin": datetime.utcnow()
                }
            }
        )
    
    @staticmethod
    def set_verified(email):
        return UserModel.collection().update_one(
            {"email": email},
            {"$set": {"isVerified": True}}
        )
    
    @staticmethod
    def add_login_device(user_id, device):
        return UserModel.collection().update_one(
            {"_id": ObjectId(user_id)},
            {
                "$push": {"devices": device},
                "$set": {
                    "last_active_device": device,
                    "last_login": device["login_time"]
                }
            }
        )

    @staticmethod
    def get_device_info(request):
        user_agent = request.headers.get('User-Agent', 'Unknown Device')
        ip_address = request.remote_addr or 'Unknown IP'
        login_time = datetime.utcnow()
        return {
            "user_agent": user_agent,
            "ip_address": ip_address,
            "login_time": login_time
        }
    
    @staticmethod
    def update_last_active_device(user_id, device: dict):
        return UserModel.collection().update_one(
            {"_id": user_id},
            {
                "$set": {
                    "last_active_device": {
                        "ip": device.get("ip"),
                        "device_type": device.get("device_type"),
                        "device_name": device.get("device_name"),
                        "os": device.get("os"),
                        "browser": device.get("browser"),
                        "login_time": datetime.utcnow()
                    },
                    "last_login": datetime.utcnow()
                }
            }
        )

    @staticmethod
    def update_user(user_id, updates: dict):
        return UserModel.collection().update_one(
            {"_id": user_id},
            {"$set": updates}
        )
    
    @staticmethod
    def hash_password(password):
        return generate_password_hash(password)


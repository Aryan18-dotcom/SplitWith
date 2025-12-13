from flask import Blueprint, request, render_template, redirect, make_response, url_for, flash
from ...models.userModel import UserModel
from ...models.expenseModel import ExpenseModel
from ...models.groupModel import GroupModel
from config import Config
from datetime import datetime, timedelta, timezone
from ..userAuth import get_session_user
import logging
from ...utils.detact_device import get_readable_device

settings_bp = Blueprint("settings", __name__, template_folder="templates")

logger = logging.getLogger(__name__)


@settings_bp.route('/settings')
def settings():
    user_session = get_session_user()
    if not user_session:
        return render_template(
            "user_auth/login.html",
            message="Please login first.",
            category="error"
        )

    user_id = str(user_session["user_id"])

    # Fetch user
    try:
        current_user = UserModel.get_user_by_ID(user_id)
        if not current_user:
            flash("User not found.", "error")
            return redirect(url_for("userAuth.login"))
    except Exception:
        flash("Unable to load user data.", "error")
        return redirect(url_for("userAuth.login"))

    context = {
        "current_user": current_user,
        "active_page": "settings"
    }

    return render_template("dashboard/setting.html", **context)


@settings_bp.route('/settings/profile', methods=['POST', 'GET'])
def settings_profile():
    user_session = get_session_user()
    if not user_session:
        return render_template(
            "user_auth/login.html",
            message="Please login first.",
            category="error"
        )

    user_id = str(user_session["user_id"])

    # Fetch user
    try:
        current_user = UserModel.get_user_by_ID(user_id)
    except Exception:
        flash("Unable to load user data.", "error")
        return redirect(url_for("userAuth.login"))

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        profile_pic = request.files.get('profile_pic')
        phone_no = request.form.get('phone_no')

        updates = {}

        if full_name:
            updates['full_name'] = full_name

        if profile_pic:
            import os
            upload_folder = "static/uploads/users_profile_pic"
            os.makedirs(upload_folder, exist_ok=True)

            filename = f"profile_{user_id}.png"
            file_path = os.path.join(upload_folder, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            profile_pic.save(file_path)

            updates['profile_pic'] = f"/{file_path.replace(os.sep, '/')}"

        if phone_no:
            updates['phone_no'] = phone_no

        if updates:
            try:
                UserModel.collection().update_one(
                    {"_id": current_user["_id"]},
                    {"$set": updates}
                )
                flash("Profile updated successfully!", "success")
                return redirect(url_for("settings.settings"))
            except Exception:
                flash("Failed to update profile. Please try again.", "error")
                return redirect(url_for("settings.setings_profile"))

    context = {
        "current_user": current_user,
        "active_page": "settings"
    }

    return render_template("dashboard/setting_profile.html", **context)


@settings_bp.route('/settings/account', methods=['POST', 'GET'])
def settings_account():
    user_session = get_session_user()
    if not user_session:
        return render_template(
            "user_auth/login.html",
            message="Please login first.",
            category="error"
        )

    user_id = str(user_session["user_id"])

    # Fetch user
    try:
        current_user = UserModel.get_user_by_ID(user_id)
    except Exception:
        flash("Unable to load user data.", "error")
        return redirect(url_for("userAuth.login"))

    if request.method == 'POST':
        updates = {}
        new_username = request.form.get('username')
        phone_no = request.form.get('phone_no')
        new_email = request.form.get('email')

        # Update username
        if new_username and new_username != current_user.get('username'):
            updates['username'] = new_username
            # Update session username
            user_session['username'] = new_username

        # Update phone number
        if phone_no and phone_no != current_user.get('phone_no'):
            updates['phone_no'] = phone_no

        # Update additional email
        if new_email:
            current_emails = current_user.get('emails', [])
            if new_email not in current_emails:
                current_emails.append(new_email)
                updates['emails'] = current_emails

        # Apply updates
        if updates:
            try:
                UserModel.collection().update_one(
                    {"_id": current_user["_id"]},
                    {"$set": updates}
                )
                flash("Account updated successfully!", "success")
                return redirect(url_for("settings.settings"))
            except Exception as e:
                flash("Failed to update account. Please try again.", "error")

    context = {
        "current_user": current_user,
        "active_page": "settings"
    }

    return render_template("dashboard/setting_account.html", **context)

@settings_bp.route('/settings/security', methods=['POST', 'GET'])
def settings_security():
    user_session = get_session_user()
    if not user_session:
        return render_template(
            "user_auth/login.html",
            message="Please login first.",
            category="error"
        )

    user_id = str(user_session["user_id"])

    # Fetch User
    try:
        current_user = UserModel.get_user_by_ID(user_id)
    except Exception:
        flash("Unable to load user data.", "error")
        return redirect(url_for("userAuth.login"))

    if request.method == 'POST':

        action = request.form.get("action")

        # ------------------------------
        # 1️⃣ CHANGE PASSWORD
        # ------------------------------
        if not action:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_new_password')

            if not current_password or not new_password or not confirm_password:
                flash("All password fields are required.", "error")
                return redirect(url_for("settings.settings"))

            if new_password != confirm_password:
                flash("New passwords do not match.", "error")
                return redirect(url_for("settings.settings"))

            from werkzeug.security import check_password_hash, generate_password_hash

            if not check_password_hash(current_user['password'], current_password):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("settings.settings"))

            hashed_new_password = generate_password_hash(new_password)

            UserModel.collection().update_one(
                {"_id": current_user["_id"]},
                {
                    "$set": {
                        "password": hashed_new_password,
                        "password_last_changed": datetime.utcnow()
                    }
                }
            )
            flash("Password updated successfully!", "success")
            return redirect(url_for("settings.settings"))

        # ------------------------------
        # 2️⃣ ENABLE 2FA
        # ------------------------------
        if action == "enable_2fa":
            UserModel.collection().update_one(
                {"_id": current_user["_id"]},
                {"$set": {"2fa_enabled": True, "2fa_method": "email"}}
            )
            flash("Two-Factor Authentication enabled!", "success")
            return redirect(url_for("settings.settings"))

        # ------------------------------
        # 3️⃣ DISABLE 2FA
        # ------------------------------
        if action == "disable_2fa":
            UserModel.collection().update_one(
                {"_id": current_user["_id"]},
                {"$set": {"2fa_enabled": False}}
            )
            flash("Two-Factor Authentication disabled.", "success")
            return redirect(url_for("settings.settings"))

        # ------------------------------
        # 4️⃣ UPDATE SECURITY QUESTIONS
        # ------------------------------
        if action == "update_security_questions":
            from werkzeug.security import generate_password_hash

            security_questions = []

            for i in range(3):
                q = request.form.get(f"question_{i}", "").strip()
                a = request.form.get(f"answer_{i}", "").strip()

                if q and a:
                    security_questions.append({
                        "question": q,
                        "answer_hash": generate_password_hash(a)
                    })

            UserModel.collection().update_one(
                {"_id": current_user["_id"]},
                {"$set": {"security_questions": security_questions}}
            )

            flash("Security questions updated successfully!", "success")
            return redirect(url_for("settings.settings"))

        # ------------------------------
        # 5️⃣ UPDATE ACCOUNT ACTIVITY ALERTS
        # ------------------------------
        if action == "update_alerts":
            alerts = current_user["account_activity_alerts"]

            updated_alerts = {
                key: (request.form.get(f"alert_{key}") == "on")
                for key in alerts
            }

            UserModel.collection().update_one(
                {"_id": current_user["_id"]},
                {"$set": {"account_activity_alerts": updated_alerts}}
            )

            flash("Account activity alerts updated!", "success")
            return redirect(url_for("settings.settings"))

    # ------------------------------
    # GET: Render UI
    # ------------------------------
    context = {
        "current_user": current_user,
        "active_page": "settings"
    }

    return render_template("dashboard/setting_security.html", **context)


@settings_bp.route('/settings/activity_log')
def settings_activity_log():
    user_session = get_session_user()
    if not user_session:
        return render_template(
            "user_auth/login.html",
            message="Please login first.",
            category="error"
        )

    user_id = str(user_session["user_id"])

    # Fetch user
    try:
        current_user = UserModel.get_user_by_ID(user_id)
    except Exception:
        flash("Unable to load user data.", "error")
        return redirect(url_for("userAuth.login"))

    activity_logs = current_user.get('last_active_device', [])
    print(activity_logs)

    context = {
        "current_user": current_user,
        "activity_logs": activity_logs,
        "active_page": "settings"
    }

    return render_template("dashboard/setting_activity_log.html", **context)    
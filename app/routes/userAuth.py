from flask import Blueprint, request, render_template, redirect, make_response, url_for, flash, session
from ..models.userModel import UserModel
from ..models.otpModel import OTPModel
import jwt
from config import Config
from datetime import datetime, timedelta, timezone
from werkzeug.security import check_password_hash
from ..utils.detact_device import get_readable_device

user_bp = Blueprint("userAuth", __name__, template_folder="templates")


# ----------------------- SIGNUP -----------------------
@user_bp.route('/auth/signup', methods=["POST", "GET"])
def signup():
    if request.method == "POST":
        data = request.form

        username = data.get('username')
        email = data.get('email').lower().strip()
        full_name = data.get('full_name')
        phone_no = data.get('phone_no')
        password = data.get('password')

        # Validate
        if not all([username, email, full_name, phone_no, password]):
            flash("Please fill all required fields!", "error")
            return render_template("user_auth/signup.html")

        # Duplicate Check (case insensitive)
        if UserModel.find_by_email_or_username(email) or UserModel.find_by_email_or_username(username):
            flash("Username or Email already exists!", "error")
            return render_template("user_auth/signup.html")

        # Store user fields temporarily in session
        session['pending_signup'] = {
            "email": email,
            "username": username,
            "full_name": full_name,
            "phone_no": phone_no,
            "password": password
        }

        # Send OTP
        OTPModel.generate_otp(email)

        flash("OTP sent to your email.", "success")
        return render_template("user_auth/verify_otp.html", email=email)

    return render_template("user_auth/signup.html")


# ----------------------- JWT FUNCTIONS -----------------------
def SetAndGetSession(payload=None, token=None):
    if token:
        try:
            decoded = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
            return {"status": True, "type": "decoded", "data": decoded}
        except jwt.ExpiredSignatureError:
            return {"status": False, "error": "Token expired"}
        except jwt.InvalidTokenError:
            return {"status": False, "error": "Invalid token"}

    if payload:
        payload["exp"] = datetime.now(timezone.utc) + timedelta(days=7)
        encoded = jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")
        return {"status": True, "type": "encoded", "token": encoded}

    return {"status": False, "error": "Provide payload or token"}


def get_session_user():
    token = request.cookies.get("session_token")
    if not token:
        return None

    session = SetAndGetSession(token=token)
    if session["status"]:
        return session["data"]

    return None



# ----------------------- LOGIN -----------------------
@user_bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    if get_session_user():
        return redirect(url_for('home.dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('user_name_or_email')
        password = request.form.get('user_password')

        if not identifier or not password:
            flash("Please fill all fields!", "error")
            return render_template("user_auth/login.html")

        # Fetch user by email or username
        user = UserModel.find_by_email_or_username(identifier)

        if not user:
            flash("Wrong credentials!", "error")
            return render_template("user_auth/login.html")

        # Check password
        if not check_password_hash(user["password"], password):
            flash("Incorrect credentials!", "error")
            return render_template("user_auth/login.html")

        # ----------------------------
        # DEVICE INFO
        # ----------------------------
        user_agent_string = request.headers.get("User-Agent")
        readable_device = get_readable_device(user_agent_string)

        current_device = {
            "ip": request.remote_addr,
            "device_type": readable_device["device_type"],
            "device_name": readable_device["device_name"],
            "os": readable_device["os"],
            "browser": readable_device["browser"],
        }

        # Check existing devices
        existing_device = next(
            (d for d in user.get("devices", [])
             if d.get("ip") == current_device["ip"]
             and d.get("device_type") == current_device["device_type"]
             and d.get("device_name") == current_device["device_name"]
             and d.get("os") == current_device["os"]
             and d.get("browser") == current_device["browser"]),
            None
        )

        if existing_device:
            existing_device["login_time"] = datetime.utcnow()
            UserModel.update_last_active_device(user_id=str(user["_id"]), device=existing_device)
        else:
            device_info = current_device.copy()
            device_info["login_time"] = datetime.utcnow()
            UserModel.add_login_device(user_id=str(user["_id"]), device=device_info)

        # Update last active device & login status
        UserModel.update_last_active_device(user_id=str(user["_id"]), device=current_device)
        UserModel.update_login_status(user_id=str(user["_id"]), is_login=True)

        # 2FA check
        if user.get('2fa_enabled'):
            # Trigger 2FA verification (default method email)
            OTPModel.generate_otp(user["email"])
            flash("2FA verification required. Check your email.", "info")
            return render_template("user_auth/verify_login.html", email=user["email"], next_url=url_for('home.dashboard'))

        # Create session
        token = SetAndGetSession({
            "user_id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"]
        })["token"]

        resp = make_response(redirect(url_for("home.dashboard")))
        resp.set_cookie("session_token", token, httponly=True, samesite="Lax")

        flash("Login successful! Welcome back.", "success")
        return resp

    return render_template("user_auth/login.html")

@user_bp.route('/auth/logout')
def logout():
    user_session = get_session_user()

    if not user_session:
        flash("You are already logged out or your session has expired.", "error")
        resp = make_response(redirect(url_for('userAuth.login')))
        resp.set_cookie("session_token", "", expires=0)
        return resp

    UserModel.update_login_status(
        user_id=user_session["user_id"],
        is_login=False
    )

    flash("Logged out successfully.", "success")

    resp = make_response(redirect(url_for('userAuth.login')))

    resp.set_cookie("session_token", "", expires=0)

    return resp

    

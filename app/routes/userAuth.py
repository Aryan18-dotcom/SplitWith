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

        # 🔄 loading = true
        response = make_response()
        response.set_cookie("loading", "true", samesite="Lax")

        data = request.form

        username = data.get('username')
        email = data.get('email', '').lower().strip()
        full_name = data.get('full_name')
        phone_no = data.get('phone_no')
        password = data.get('password')

        # ❌ Validation
        if not all([username, email, full_name, phone_no, password]):
            flash("Please fill all required fields!", "error")

            response = make_response(render_template("user_auth/signup.html"))
            response.set_cookie("loading", "false", samesite="Lax")
            return response

        # ❌ Duplicate check
        if (
            UserModel.find_by_email_or_username(email) or
            UserModel.find_by_email_or_username(username)
        ):
            flash("Username or Email already exists!", "error")

            response = make_response(render_template("user_auth/signup.html"))
            response.set_cookie("loading", "false", samesite="Lax")
            return response

        # 🗃️ Store pending signup
        session['pending_signup'] = {
            "email": email,
            "username": username,
            "full_name": full_name,
            "phone_no": phone_no,
            "password": password
        }

        # 🔐 Generate OTP
        otp = OTPModel.generate_otp(email)
        if not otp:
            flash("Failed to generate OTP. Try again.", "error")

            response = make_response(render_template("user_auth/signup.html"))
            response.set_cookie("loading", "false", samesite="Lax")
            return response

        # ✉️ Send email (SYNC)
        success = OTPModel.send_email(email, otp)

        if not success:
            flash("Failed to send OTP email. Try again.", "error")

            response = make_response(render_template("user_auth/signup.html"))
            response.set_cookie("loading", "false", samesite="Lax")
            return response

        # ✅ SUCCESS
        flash("OTP sent to your email.", "success")

        response = make_response(
            render_template("user_auth/verify_otp.html", email=email)
        )
        response.set_cookie("loading", "false", samesite="Lax")
        return response

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

        # 🔄 Start loading
        response = make_response()
        response.set_cookie("loading", "true", samesite="Lax")

        identifier = request.form.get('user_name_or_email')
        password = request.form.get('user_password')

        # ❌ Validation
        if not identifier or not password:
            flash("Please fill all fields!", "error")

            response = make_response(render_template("user_auth/login.html"))
            response.set_cookie("loading", "false", samesite="Lax")
            return response

        user = UserModel.find_by_email_or_username(identifier)

        if not user or not check_password_hash(user["password"], password):
            flash("Incorrect credentials!", "error")

            response = make_response(render_template("user_auth/login.html"))
            response.set_cookie("loading", "false", samesite="Lax")
            return response

        # 📱 Device tracking
        user_agent_string = request.headers.get("User-Agent")
        readable_device = get_readable_device(user_agent_string)

        current_device = {
            "ip": request.remote_addr,
            "device_type": readable_device["device_type"],
            "device_name": readable_device["device_name"],
            "os": readable_device["os"],
            "browser": readable_device["browser"],
            "login_time": datetime.utcnow()
        }

        UserModel.update_last_active_device(
            user_id=str(user["_id"]),
            device=current_device
        )

        UserModel.update_login_status(
            user_id=str(user["_id"]),
            is_login=True
        )

        # 🔐 2FA FLOW
        if user.get('2fa_enabled'):

            # Generate OTP
            otp = OTPModel.generate_otp(user["email"])
            if not otp:
                flash("Failed to generate OTP. Try again.", "error")

                response = make_response(render_template("user_auth/login.html"))
                response.set_cookie("loading", "false", samesite="Lax")
                return response

            # Send OTP email
            success = OTPModel.send_email(user["email"], otp)
            if not success:
                flash("Failed to send OTP email. Try again.", "error")

                response = make_response(render_template("user_auth/login.html"))
                response.set_cookie("loading", "false", samesite="Lax")
                return response

            # ✅ OTP sent
            response = make_response(
                render_template(
                    "user_auth/verify_login.html",
                    email=user["email"],
                    next_url=url_for('home.dashboard')
                )
            )
            response.set_cookie("loading", "false", samesite="Lax")
            return response

        # 🔓 NO 2FA → Create session
        token = SetAndGetSession({
            "user_id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"]
        })["token"]

        response = make_response(redirect(url_for("home.dashboard")))
        response.set_cookie("session_token", token, httponly=True, samesite="Lax")

        flash("Login successful! Welcome back.", "success")

        response.set_cookie("loading", "false", samesite="Lax")
        return response

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

    

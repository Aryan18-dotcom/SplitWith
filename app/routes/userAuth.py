from flask import Blueprint, request, render_template, redirect, make_response, url_for, flash, session
from ..models.userModel import UserModel
from ..models.otpModel import OTPModel
import jwt
from config import Config
from datetime import datetime, timedelta, timezone
from werkzeug.security import check_password_hash
from ..utils.detact_device import get_readable_device

user_bp = Blueprint("userAuth", __name__, template_folder="templates")


# # ----------------------- SIGNUP -----------------------
# @user_bp.route('/auth/signup', methods=["POST", "GET"])
# def signup():
#     if request.method == "POST":

#         # Set loading = true
#         response = make_response()
#         response.set_cookie("loading", "true", samesite="Lax")

#         data = request.form

#         username = data.get('username')
#         email = data.get('email').lower().strip()
#         full_name = data.get('full_name')
#         phone_no = data.get('phone_no')
#         password = data.get('password')

#         if not all([username, email, full_name, phone_no, password]):
#             flash("Please fill all required fields!", "error")
            
#             response = make_response(render_template("user_auth/signup.html"))
#             response.set_cookie("loading", "false", samesite="Lax")
#             return response

#         if UserModel.find_by_email_or_username(email) or UserModel.find_by_email_or_username(username):
#             flash("Username or Email already exists!", "error")

#             response = make_response(render_template("user_auth/signup.html"))
#             response.set_cookie("loading", "false", samesite="Lax")
#             return response

#         # Store pending
#         session['pending_signup'] = {
#             "email": email,
#             "username": username,
#             "full_name": full_name,
#             "phone_no": phone_no,
#             "password": password
#         }

#         OTPModel.generate_otp(email)

#         flash("OTP sent to your email.", "success")

#         response = make_response(render_template("user_auth/verify_otp.html", email=email))
#         response.set_cookie("loading", "false", samesite="Lax")
#         return response

#     return render_template("user_auth/signup.html")
import threading
from flask import request, render_template, flash, make_response, redirect, url_for, session, current_app
from time import sleep # Used for the simulated timeout

# Assume user_bp and other necessary imports (UserModel, OTPModel, etc.) are present
# from . import user_bp # If this is in routes.py

# --- 1. Background Task Function ---
def _send_otp_in_background(app_context, email):
    """
    Function to be run in a separate thread.
    It holds the slow I/O operation (sending the email).
    """
    # Push the application context required for Flask-Mail or app.logger
    with app_context:
        try:
            current_app.logger.info(f"THREAD: Starting OTP send for {email}...")
            
            # --- CRITICAL BLOCKING CODE HERE ---
            # Assume OTPModel.generate_otp internally calls the email sending logic
            OTPModel.generate_otp(email)
            # -----------------------------------
            
            current_app.logger.info(f"THREAD: Successfully sent OTP for {email}.")
            
            # Optional: Add a small delay (e.g., 2 seconds) to simulate minimum time
            # and prevent an instant redirect which can feel too fast/broken.
            # However, usually the email network time is enough.
            # sleep(1) 

        except Exception as e:
            current_app.logger.error(f"THREAD ERROR: Failed to send OTP email to {email}: {e}")
            # Note: Since this is in a thread, we cannot directly flash the user.
            # A more robust system (Celery) would handle retries and error reporting.


# ----------------------- SIGNUP ROUTE -----------------------
@user_bp.route('/auth/signup', methods=["POST", "GET"])
def signup():
    if request.method == "POST":
        
        data = request.form

        username = data.get('username')
        email = data.get('email').lower().strip()
        full_name = data.get('full_name')
        phone_no = data.get('phone_no')
        password = data.get('password')

        # --- 1. Basic Validation ---
        if not all([username, email, full_name, phone_no, password]):
            flash("Please fill all required fields!", "error")
            return render_template("user_auth/signup.html")

        # --- 2. Existence Check ---
        if UserModel.find_by_email_or_username(email) or UserModel.find_by_email_or_username(username):
            flash("Username or Email already exists!", "error")
            return render_template("user_auth/signup.html")

        # --- 3. Store Pending Data ---
        session['pending_signup'] = {
            "email": email,
            "username": username,
            "full_name": full_name,
            "phone_no": phone_no,
            "password": password
        }

        # --- 4. ASYNCHRONOUS EMAIL SENDING ---
        # Get the application context to pass to the thread
        app_context = current_app.app_context()
        
        # Start the email sending in a background thread
        email_thread = threading.Thread(
            target=_send_otp_in_background, 
            args=(app_context, email)
        )
        email_thread.start()
        
        current_app.logger.info(f"MAIN: OTP send started in background for {email}. Proceeding to redirect.")

        # --- 5. IMMEDIATE REDIRECT (Fixes 'Stuck on Loading' and UX) ---
        flash("OTP has been sent to your email. Please check your inbox!", "success")
        
        # We redirect immediately, resolving the request and stopping the loader.
        # The frontend should immediately show the verify_otp page.
        response = make_response(render_template("user_auth/verify_otp.html", email=email))
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

        # Start loading
        response = make_response()
        response.set_cookie("loading", "true", samesite="Lax")

        identifier = request.form.get('user_name_or_email')
        password = request.form.get('user_password')

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

        # Device tracking
        user_agent_string = request.headers.get("User-Agent")
        readable_device = get_readable_device(user_agent_string)

        current_device = {
            "ip": request.remote_addr,
            "device_type": readable_device["device_type"],
            "device_name": readable_device["device_name"],
            "os": readable_device["os"],
            "browser": readable_device["browser"],
        }

        existing_device = next(
            (d for d in user.get("devices", []) 
             if d.get("ip") == current_device["ip"] and
                d.get("device_type") == current_device["device_type"] and
                d.get("device_name") == current_device["device_name"] and
                d.get("os") == current_device["os"] and
                d.get("browser") == current_device["browser"]),
            None
        )

        if existing_device:
            existing_device["login_time"] = datetime.utcnow()
            UserModel.update_last_active_device(user_id=str(user["_id"]), device=existing_device)
        else:
            current_device["login_time"] = datetime.utcnow()
            UserModel.add_login_device(user_id=str(user["_id"]), device=current_device)

        UserModel.update_last_active_device(user_id=str(user["_id"]), device=current_device)
        UserModel.update_login_status(user_id=str(user["_id"]), is_login=True)

        # Handle 2FA
        if user.get('2fa_enabled'):
            OTPModel.generate_otp(user["email"])

            response = make_response(render_template("user_auth/verify_login.html",
                                                     email=user["email"],
                                                     next_url=url_for('home.dashboard')))
            response.set_cookie("loading", "false", samesite="Lax")
            return response

        # Create JWT session
        token = SetAndGetSession({
            "user_id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"]
        })["token"]

        response = make_response(redirect(url_for("home.dashboard")))
        response.set_cookie("session_token", token, httponly=True, samesite="Lax")

        flash("Login successful! Welcome back.", "success")

        # Stop loading
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

    

from flask import Blueprint, request, render_template, flash, redirect, url_for, make_response, session
from ..models.userModel import UserModel
from ..models.otpModel import OTPModel
from .userAuth import SetAndGetSession

otp_bp = Blueprint("otp", __name__, template_folder="templates")


@otp_bp.route('/verify-login-2FA', methods=["POST"])
def verify_login_2FA():
    email = request.form.get('email')
    otp = request.form.get('otp')

    if not otp:
        flash("Please enter the OTP.", "error")
        return render_template("user_auth/verify_login_2FA.html", email=email)

    # Ensure OTP is number
    try:
        otp = int(otp)
    except ValueError:
        flash("Invalid OTP format.", "error")
        return render_template("user_auth/verify_login.html", email=email)

    # -----------------------------
    # Step 1: Verify OTP using model
    # -----------------------------
    success, message = OTPModel.verify_otp(email, otp)

    if not success:
        flash(message, "error")
        return render_template("user_auth/verify_login.html", email=email)

    # -----------------------------
    # Step 2: OTP matched → Log user in
    # -----------------------------
    user = UserModel.find_by_email_or_username(email)
    if not user:
        flash("Account not found!", "error")
        return redirect(url_for("userAuth.login"))

    # Create session JWT token
    session_data = {
        "user_id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"]
    }

    token = SetAndGetSession(session_data)["token"]

    resp = make_response(redirect(url_for("home.dashboard")))
    resp.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="Lax"
    )

    # Mark user as logged in
    UserModel.update_login_status(user_id=str(user["_id"]), is_login=True)

    flash("Login successful!", "success")
    return resp


# ----------------------- VERIFY OTP -----------------------
@otp_bp.route('/verify-otp', methods=["POST"])
def verify_otp():
    email = request.form.get('email')
    otp = request.form.get('otp')

    if not otp:
        flash("Please enter the OTP.", "error")
        return render_template("user_auth/verify_otp.html", email=email)

    try:
        otp = int(otp)
    except:
        flash("Invalid OTP format.", "error")
        return render_template("user_auth/verify_otp.html", email=email)

    # Get stored signup data
    pending_data = session.get("pending_signup")
    if not pending_data:
        flash("Signup session expired. Please register again.", "error")
        return redirect(url_for("userAuth.signup"))

    # Verify OTP
    success, message = OTPModel.verify_otp(email, otp)
    if not success:
        flash(message, "error")
        return render_template("user_auth/verify_otp.html", email=email)

    # Create user only after OTP verification
    UserModel.create_user(
        email=pending_data["email"],
        username=pending_data["username"],
        full_name=pending_data["full_name"],
        phone_no=pending_data["phone_no"],
        password=pending_data["password"],
    )

    UserModel.set_verified(email)

    # Cleanup
    session.pop("pending_signup", None)

    flash("Signup successful! You can now log in.", "success")
    return redirect(url_for("userAuth.login"))



# ----------------------- RESEND OTP -----------------------
@otp_bp.route('/resend-otp', methods=["POST"])
def resend_otp():
    email = request.form.get('email')

    if not email:
        flash("Email not found!", "error")
        return redirect(url_for("userAuth.signup"))

    # Resend OTP
    OTPModel.resend_otp(email)

    # Carry hidden fields again
    user_data = {
        key: request.form.get(key)
        for key in ['username', 'full_name', 'phone_no', 'password']
    }

    flash("OTP resent successfully! Check your email.", "success")
    return render_template("user_auth/verify_otp.html", email=email, **user_data)

# ----------------------- RESEND OTP -----------------------
@otp_bp.route('/resend-otp/login_verification', methods=["POST"])
def resend_otp_verification():
    email = request.form.get('email')

    if not email:
        flash("Email not found!", "error")
        return redirect(url_for("userAuth.signup"))

    # Resend OTP
    OTPModel.resend_otp(email)

    # Carry hidden fields again
    user_data = {
        key: request.form.get(key)
        for key in ['username', 'full_name', 'phone_no', 'password']
    }

    flash("OTP resent successfully! Check your email.", "success")
    return render_template("user_auth/verify_login.html", email=email, **user_data)

from flask import Blueprint, request, render_template, redirect, make_response, url_for, flash
from ...models.userModel import UserModel
from ...models.expenseModel import ExpenseModel
from ...models.groupModel import GroupModel
from config import Config
from datetime import datetime, timedelta, timezone
from ..userAuth import get_session_user
import logging
from ...utils.detact_device import get_readable_device
from .groupRoute import compute_member_balances

home_bp = Blueprint("home", __name__, template_folder="templates")

logger = logging.getLogger(__name__)


@home_bp.app_template_filter('datetimeformat')
def datetimeformat(value, format="%d %b, %I:%M %p"):
    if not value:
        return ""
    try:
        # Accept both timestamp, string, or datetime
        if isinstance(value, (int, float)):
            dt = datetime.utcfromtimestamp(float(value))
        elif isinstance(value, str):
            try:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = datetime.fromisoformat(value)
        else:
            dt = value  # assume it's already a datetime
        return dt.strftime(format)
    except Exception:
        return value


@home_bp.app_template_filter('currency')
def currency_filter(value, symbol="₹"):
    try:
        v = float(value)
        return f"{symbol}{v:,.2f}"
    except Exception:
        return f"{symbol}0.00"


@home_bp.route('/dashboard')
def dashboard():
    user_session = get_session_user()
    if not user_session:
        # Not logged in
        return render_template(
            "user_auth/login.html",
            message="Please login first.",
            category="error"
        )

    user_id = str(user_session["user_id"])

    try:
        current_user = UserModel.get_user_by_ID(user_id)
    except Exception:
        flash("Unable to load user data.", "error")
        return redirect(url_for("user_auth.login"))

    # Fetch all active users and groups
    users = UserModel.get_all_active_users_except(user_id) or []
    users_map = { str(u["_id"]): u for u in users }
    groups = GroupModel.get_user_groups_with_users(user_id) or []
    groups_map = { str(g["_id"]): g for g in groups }

    # Recent transactions (last 10)
    raw_transactions = ExpenseModel.get_expenses_for_user(user_id) or []
    transactions = []
    for tx in raw_transactions:
        group_name = None
        if tx.get("group_id"):
            group = groups_map.get(str(tx["group_id"]))
            group_name = group["group_title"] if group else "Unknown Group"
        transactions.append({
            "transection_id": tx.get("_id", "undefind"),
            "title": tx.get("title", "Untitled"),
            "amount": float(tx.get("amount", 0)),
            "description": tx.get("description", ""),
            "group_name": group_name,
            "created_at": tx.get("created_at"),
            "payer_id": str(tx.get("created_by")) if tx.get("created_by") else None
        })

    # Recent expenses (for sidebar)
    raw_recent_expenses = ExpenseModel.get_expenses_for_user(user_id) or []
    recent_expenses = []
    for exp in raw_recent_expenses:
        group_details = None
        if exp.get("group_id"):
            g = groups_map.get(str(exp["group_id"]))
            if g:
                group_details = g
        recent_expenses.append({
            "title": exp.get("title", "Untitled"),
            "amount": float(exp.get("amount", 0)),
            "description": exp.get("description", ""),
            "group_details": group_details,
            "created_at": exp.get("created_at")
        })

    # Most active groups
    raw_active_groups = ExpenseModel.get_most_active_groups_for_user(user_id, limit=3) or []
    active_groups = []

    for g in raw_active_groups:

        group_obj = groups_map.get(str(g["_id"]))
        if not group_obj:
            continue

        # compute current user's balance in this group
        member_balances = compute_member_balances(g["_id"])
        balance = member_balances.get(str(user_id), 0.0)

        active_groups.append({
            "group_name": group_obj["group_title"],
            "members": len(group_obj.get("group_members", [])),
            "expense_count": g.get("expense_count") or 0,
            "balance": balance
        })


    # Monthly aggregated expenses
    monthly_data = ExpenseModel.get_monthly_expenses_for_user(user_id) or []

    # Extract actual month from "_id.month"
    months = [m["_id"].get("month", "") for m in monthly_data]

    # Extract correct amount
    monthly_expenses = [float(m.get("total_amount", 0)) for m in monthly_data]


    # Total balances
    try:
        total_owed = float(ExpenseModel.get_total_owed_to_user(user_id) or 0)
    except Exception:
        total_owed = 0
    try:
        total_owes = float(ExpenseModel.get_total_user_owes(user_id) or 0)
    except Exception:
        total_owes = 0
    total_balance = total_owed - total_owes

    context = {
        "current_user": current_user,
        "current_user_id": user_id,
        "transactions": transactions,
        "recent_expenses": recent_expenses,
        "active_groups": active_groups,
        "months": months,
        "monthly_expenses": monthly_expenses,
        "users": users,
        "groups": groups,
        "total_balance": total_balance,
        "total_owed": total_owed,
        "total_owes": total_owes,
        "active_page": "dashboard"
    }

    return render_template("dashboard/dashboard.html", **context)

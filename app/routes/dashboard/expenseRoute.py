# expenseRoute.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from ...models.expenseModel import ExpenseModel
from ...models.userModel import UserModel
from ...models.groupModel import GroupModel
from ..userAuth import get_session_user
from datetime import datetime

expense_bp = Blueprint("expense", __name__)


# ---------------------------------------------------------
# Helper: Get logged-in user
# ---------------------------------------------------------
def get_current_user():
    session = get_session_user()
    if not session:
        return None
    return UserModel.get_user_by_ID(str(session["user_id"]))


# ---------------------------------------------------------
# Helper: Normalize member list based on UI flow
# ---------------------------------------------------------
def get_members_for_expense(group_id, member_id, current_user_id):
    if member_id:
        return [current_user_id, member_id]

    if group_id:
        grp = GroupModel.get_group_by_id(group_id)
        return [str(x) for x in grp.get("group_members", [])]

    # fallback: only current user
    return [current_user_id]


# ---------------------------------------------------------
# Route: All expenses of logged-in user
# ---------------------------------------------------------
@expense_bp.route("/expenses")
def expenses():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for("userAuth.login"))

    user_id = str(current_user["_id"])

    expenses = ExpenseModel.get_expenses_for_user(user_id)
    users = {str(u["_id"]): u for u in UserModel.get_all_users()}
    groups = {str(g["_id"]): g for g in GroupModel.get_all_groups()}

    return render_template("dashboard/expenses.html",
                           expenses=expenses,
                           users=users,
                           groups=groups,
                           current_user=current_user,
                           user_id=user_id)


# ---------------------------------------------------------
# CREATE EXPENSE (Unified — no step1/step2 mess)
# ---------------------------------------------------------
from datetime import datetime
from flask import request, redirect, url_for, flash, render_template

@expense_bp.route("/expense/create", methods=["GET", "POST"])
def create_expense():
    session_user = get_session_user()
    if not session_user:
        return redirect(url_for("userAuth.login"))

    current_user_id = str(session_user["user_id"])
    current_user = UserModel.get_user_by_ID(current_user_id)

    # 🔒 Ensure safe Jinja rendering
    current_user["_id"] = str(current_user["_id"])

    # =========================
    # GET REQUEST
    # =========================
    if request.method == "GET":
        groups = GroupModel.get_user_groups(current_user_id)
        users = UserModel.get_all_users()

        # ✅ Sanitize groups for Jinja + tojson
        sanitized_groups = []
        for g in groups:
            g["_id"] = str(g["_id"])

            # group_members may contain ObjectId
            members = []
            for m in g.get("group_members", []):
                members.append(str(m))

            g["group_members"] = members

            # OPTIONAL: if you store populated objects
            if "group_members_objects" in g:
                clean_objects = []
                for u in g["group_members_objects"]:
                    u["_id"] = str(u["_id"])
                    clean_objects.append(u)
                g["group_members_objects"] = clean_objects

            sanitized_groups.append(g)

        # ✅ Sanitize users
        sanitized_users = []
        for u in users:
            u["_id"] = str(u["_id"])
            if u["_id"] != current_user_id:
                sanitized_users.append(u)

        return render_template(
            "dashboard/create_expense.html",
            current_user=current_user,
            groups=sanitized_groups,
            users=sanitized_users,
            form_step=1
        )

    # =========================
    # POST REQUEST
    # =========================
    title = request.form.get("title", "").strip()

    try:
        amount = float(request.form.get("amount", 0))
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash("Please enter a valid amount", "danger")
        return redirect(url_for("expense.create_expense"))

    description = request.form.get("description", "").strip()
    group_id = request.form.get("group_id")
    member_id = request.form.get("member_id")

    members = []
    payer = current_user_id
    split_type = "paid_by_me"

    # =========================
    # PERSONAL EXPENSE
    # =========================
    if member_id:
        other_id = str(member_id)
        members = sorted([current_user_id, other_id])

        other_user = UserModel.get_user_by_ID(other_id)
        if not other_user:
            flash("User not found", "danger")
            return redirect(url_for("expense.create_expense"))

        group_name_for_check = (
            f"Personal Group({current_user['username']} - {other_user['username']})"
        )

        existing = GroupModel.get_personal_group(
            user_ids_sorted=members,
            group_name=group_name_for_check
        )

        if existing:
            group_id = str(existing["_id"])
        else:
            group_id = GroupModel.create_group(
                created_by=current_user_id,
                title=f"Personal Group({current_user['username']} - {other_user['username']})",
                description="Personal group between two users",
                members=members,
                is_personal=True
            )

        ui_split = request.form.get("split_type", "paid_by_me")

        if ui_split == "paid_by_other":
            split_type = "paid_by_other"
            payer = request.form.get("paid_by") or other_id
        elif ui_split in ("custom", "equal"):
            split_type = ui_split
        else:
            split_type = "paid_by_me"
            payer = current_user_id

    # =========================
    # GROUP EXPENSE
    # =========================
    elif group_id:
        group = GroupModel.get_group_by_id(group_id)
        if not group:
            flash("Group not found", "danger")
            return redirect(url_for("expense.create_expense"))

        members = [str(m) for m in group.get("group_members", [])]

        ui_split = (
            request.form.get("split_type")
            or request.form.get("dynamicSplitType")
            or "equal"
        )

        if ui_split == "paid_by_other":
            split_type = "paid_by_other"
            payer = request.form.get("paid_by") or current_user_id
        elif ui_split in ("custom", "equal"):
            split_type = ui_split
        else:
            split_type = "paid_by_me"
            payer = current_user_id

    # =========================
    # FALLBACK (SAFETY)
    # =========================
    else:
        members = [current_user_id]
        split_type = "paid_by_me"
        payer = current_user_id
        group_id = None

    # =========================
    # CUSTOM PAYMENTS & SHARES
    # =========================
    custom_payments = {}
    custom_shares = {}

    for m in members:
        m = str(m)
        try:
            custom_payments[m] = float(request.form.get(f"pay_{m}", 0))
        except ValueError:
            custom_payments[m] = 0.0

        try:
            custom_shares[m] = float(request.form.get(f"share_{m}", 0))
        except ValueError:
            custom_shares[m] = 0.0

    # =========================
    # OVERRIDE FOR SIMPLE SPLITS
    # =========================
    if split_type in ("paid_by_me", "paid_by_other"):
        custom_payments = {m: 0.0 for m in members}
        custom_payments[str(payer)] = amount

    # =========================
    # FINAL SPLIT
    # =========================
    final_split = ExpenseModel.calculate_split(
        amount=amount,
        members=members,
        split_type=split_type,
        payer=payer,
        custom_shares=custom_shares,
        custom_payments=custom_payments
    )

    # =========================
    # DATABASE OPERATIONS
    # =========================
    if group_id:
        GroupModel.add_total_balance(group_id=group_id, amount=amount)

    ExpenseModel.create_expense({
        "title": title,
        "amount": amount,
        "group_id": group_id,
        "created_by": current_user_id,
        "split_type": split_type,
        "split_with": members,
        "custom_payments": custom_payments,
        "custom_shares": custom_shares,
        "final_split": final_split,
        "description": description,
        "created_at": datetime.utcnow()
    })

    flash("Expense added successfully!", "success")
    return redirect(url_for("expense.expenses"))

    # print({
    #     "title": title,
    #     "amount": amount,
    #     "group_id": group_id,
    #     "created_by": current_user_id,
    #     "split_type": split_type,
    #     "split_with": members,
    #     "custom_payments": custom_payments,
    #     "custom_shares": custom_shares,
    #     "final_split": final_split,
    #     "description": description,
    #     "created_at": datetime.utcnow()
    # })



# ---------------------------------------------------------
# View Specific Expense
# ---------------------------------------------------------
@expense_bp.route("/expense/<expense_id>")
def view_expense(expense_id):
    # Get current user
    user_session = get_session_user()
    if not user_session:
        return redirect(url_for("userAuth.login"))

    current_user = UserModel.get_user_by_ID(str(user_session["user_id"]))
    current_user_id = str(current_user["_id"])

    # Fetch expense
    exp = ExpenseModel.get_by_id(expense_id)
    print(exp)
    if not exp:
        flash("Expense not found.", "error")
        return redirect(url_for("expense.expenses"))

    # Users map
    users = {str(u["_id"]): u for u in UserModel.get_all_users()}

    # Group
    group = None
    if exp.get("group_id"):
        group = GroupModel.find_by_id(exp["group_id"])

    # -----------------------------
    # 1️⃣ PAYMENT MAP (PAID BY)
    # -----------------------------
    paid_map = {}
    for uid, split in exp["final_split"].items():
        paid_map[uid] = float(split.get("paid", 0))

    # -----------------------------
    # 2️⃣ BUILD ACTUAL WHO-OWES-WHOM
    # -----------------------------
    split_details = []

    # list of (uid, net) pairs
    nets = {uid: float(data["net_balance"]) for uid, data in exp["final_split"].items()}

    # creditors = +ve balance  
    # debtors = -ve balance  
    creditors = [(uid, amt) for uid, amt in nets.items() if amt > 0]
    debtors   = [(uid, amt) for uid, amt in nets.items() if amt < 0]

    # Match debtors → creditors
    ci = 0
    di = 0

    while di < len(debtors) and ci < len(creditors):
        debtor, d_amt = debtors[di]
        creditor, c_amt = creditors[ci]

        pay_amount = min(-d_amt, c_amt)

        split_details.append({
            "from_user": debtor,
            "to_user": creditor,
            "amount": pay_amount
        })

        # update balances
        nets[debtor] += pay_amount
        nets[creditor] -= pay_amount

        if nets[debtor] == 0:
            di += 1
        if nets[creditor] == 0:
            ci += 1

    # -----------------------------
    # 3️⃣ SUMMARY FOR CURRENT USER
    # -----------------------------
    you_owe = sum(item["amount"] for item in split_details if item["from_user"] == current_user_id)
    you_are_owed = sum(item["amount"] for item in split_details if item["to_user"] == current_user_id)

    # For group footer card
    user_net = exp["final_split"][current_user_id]["net_balance"]

    expense_for_template = exp.copy()
    expense_for_template.update({
        "custom_split": paid_map,          # paid amounts
        "split_details": split_details,    # who owes whom
        "you_owe": you_owe,
        "you_are_owed": you_are_owed,
    })

    return render_template(
        "dashboard/view_expense.html",
        expense=expense_for_template,
        users=users,
        group=group,
        current_user=current_user,
        current_user_id=current_user_id,
        net_balance=user_net,               # for group section
    )



# ---------------------------------------------------------
# Delete Expense
# ---------------------------------------------------------
@expense_bp.route("/expense/delete/<expense_id>", methods=["POST"])
def delete_expense(expense_id):
    ExpenseModel.delete_expense(expense_id)
    flash("Expense deleted!", "success")
    return redirect(url_for("expense.expenses"))

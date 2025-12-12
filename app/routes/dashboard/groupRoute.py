from flask import Blueprint, request, render_template, redirect, url_for, flash
from ...models.groupModel import GroupModel
from ..userAuth import get_session_user
from ...models.userModel import UserModel
from ...models.expenseModel import ExpenseModel
from ...utils.mailer import send_email
import urllib.parse
from ...utils.save_photo import save_group_photo
from datetime import datetime

group_bp = Blueprint("group", __name__, template_folder="templates/dashboard/groups")


# ------------- CREATE GROUP (now sends invites) -------------
@group_bp.route('/groups/create', methods=['GET', 'POST'])
def create_group():
    user_session = get_session_user()
    users = UserModel.get_all_users()
    current_user = UserModel.get_user_by_ID(user_session["user_id"]) if user_session else None

    if not user_session:
        return render_template("user_auth/login.html", message="Please login first.", category="error")

    if request.method == 'POST':
        title = request.form.get("group_title")
        description = request.form.get("group_description")
        photo = request.files.get("group_photo")
        selected_members = request.form.getlist("members") or []  # list of user_id strings

        if not title or not description:
            flash("Title and description are required.", "error")
            return redirect(url_for("group.create_group"))
        

        creator_id = str(user_session["user_id"])
        # # Ensure creator is part of the group members list
        if creator_id not in selected_members:
            selected_members.append(creator_id)

        # Create group with creator + (optionally) those members already accepted.
        # We'll create group with creator only, then invite others.
        new_group_id = GroupModel.create_group(
            created_by=creator_id,
            title=title,
            description=description,
            group_photo = save_group_photo(photo) if photo else None,
            members=[creator_id]  # only creator initially
        )

        # Send invites to other selected members (excluding creator)
        for member_id in selected_members:
            if str(member_id) == creator_id:
                continue
            user = UserModel.get_user_by_ID(member_id)
            if not user:
                continue

            # If user is already a member (shouldn't be), skip
            # but group currently only has creator, however keep the safety check

            # Create invite token and link
            token = GroupModel.create_invite_token(new_group_id, member_id)
            # Build absolute join URL
            join_path = url_for("group.join_with_token", token=token)
            join_url = urllib.parse.urljoin(request.url_root, join_path)

            # Email content (simple)
            subject = f"You've been invited to join '{title}'"
            html_body = f"""
                <p>Hi {user.get('username','')}</p>
                <p>You were invited to join the group <strong>{title}</strong> on our app.</p>
                <p><a href="{join_url}">Click here to join the group</a></p>
                <p>If you didn't expect this invite, ignore this email.</p>
            """
            plain_body = f"Join {title}: {join_url}"

            ok, err = send_email(user.get("email"), subject, html_body=html_body, plain_body=plain_body)
            if not ok:
                # Log or flash — do not break group creation
                print(f"Failed to send invite to {user.get('email')}: {err}")

        flash("Group created and invites sent (if emails available).", "success")
        return redirect(url_for("group.list_groups"))

    return render_template("dashboard/create_group.html", users=users, current_user=current_user)


# ------------- LIST GROUPS -------------
@group_bp.route('/groups')
def list_groups():
    user_session = get_session_user()
    if not user_session:
        flash("Please login first.", "error")
        return redirect(url_for("user_auth.login"))

    try:
        current_user = UserModel.get_user_by_ID(user_session["user_id"])
    except Exception as e:
        print(e)
        flash("Unable to load user data.", "error")
        return redirect(url_for("user_auth.login"))

    groups = GroupModel.get_user_groups_with_users(user_session["user_id"])
    current_user_id = str(user_session["user_id"])

    # Compute total_balance for each group for current user
    for group in groups:
        member_balances = compute_member_balances(group['_id'])
        group['total_balance'] = member_balances.get(current_user_id, 0.0)

    return render_template(
        "dashboard/groups.html",
        groups=groups,
        current_user=current_user,
        current_user_id=current_user_id
    )

# Helper function to compute net balance per member in a group
def compute_member_balances(group_id):
    balances = {}
    expenses = list(
        ExpenseModel.collection().find({"group_id": str(group_id)})
    )
    for expense in expenses:
        fs = expense.get("final_split", {})
        for uid, data in fs.items():
            uid = str(uid)
            balances[uid] = balances.get(uid, 0.0) + float(data.get("net_balance", 0.0))
    return balances



@group_bp.app_template_filter('datetimeformat')
def datetimeformat(value, format="%d %b"):
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


# ------------- GROUP DETAILS -------------
@group_bp.route("/groups/<group_id>")
def group_details(group_id):
    user_session = get_session_user()
    if not user_session:
        flash("Please login first.", "error")
        return redirect(url_for("user_auth.login"))

    # Load current user
    try:
        current_user = UserModel.get_user_by_ID(user_session["user_id"])
    except Exception:
        flash("Unable to load user data.", "error")
        return redirect(url_for("user_auth.login"))

    # Load group
    group = GroupModel.find_by_id(group_id)
    if not group:
        return "Group not found", 404

    # Users map
    users_map = {str(u["_id"]): u for u in UserModel.get_all_users()}
    current_user_id = str(user_session["user_id"])

    # Build members list for UI
    members = []
    for uid in group.get("group_members", []):
        uid = str(uid)
        if uid in users_map:
            u = users_map[uid]
            members.append({
                "id": uid,
                "name": u.get("full_name") or u.get("username"),
                "email": u.get("email"),
                "profile_pic": u.get("profile_pic"),
                "joined_at": u.get("created_at"),
                "role": "Creator" if uid == str(group["created_by"]) else "Member",
            })

    creator = users_map.get(str(group["created_by"]))

    # Load all expenses
    expenses = list(
        ExpenseModel.collection()
        .find({"group_id": str(group_id)})
        .sort("created_at", -1)
    )

    # Compute balances
    member_balances = {}  # net balance per member
    payment_tracker = {}  # total paid per member
    total_expenses = 0.0

    # Store share holding per user
    share_holding_map = {}

    for expense in expenses:
        amount = float(expense.get("amount", 0))
        total_expenses += amount
        fs = expense.get("final_split", {})
        custom_shares = expense.get("custom_shares", {})

        for uid, data in fs.items():
            uid = str(uid)
            paid = float(data.get("paid", 0))
            net_balance = float(data.get("net_balance", 0))
            should_pay = float(data.get("should_pay", 0))

            payment_tracker[uid] = payment_tracker.get(uid, 0.0) + paid
            member_balances[uid] = member_balances.get(uid, 0.0) + net_balance

            # share holding
            if amount > 0:
                share_holding_map[uid] = round((should_pay / amount) * 100, 0)

    final_split_current_user = member_balances.get(current_user_id, 0.0)

    # -----------------------------------------------------------
    # PAYMENT BREAKDOWN
    # -----------------------------------------------------------
    payment_breakdown = []
    for uid in group.get("group_members", []):
        uid = str(uid)
        name = "You" if uid == current_user_id else users_map[uid].get("full_name") or users_map[uid].get("username")
        payment_breakdown.append(f"{name} paid ₹{payment_tracker.get(uid, 0.0):.2f}")

    # -----------------------------------------------------------
    # SHARE HOLDING
    # -----------------------------------------------------------
    share_holding = []
    for uid in group.get("group_members", []):
        uid = str(uid)
        name = "You" if uid == current_user_id else users_map[uid].get("full_name") or users_map[uid].get("username")
        share = share_holding_map.get(uid, 0)
        share_holding.append(f"{name} {share:.0f}%")

    # -----------------------------------------------------------
    # WHO OWES WHOM
    # -----------------------------------------------------------
    owes_you = []
    you_owe = []

    for uid, balance in member_balances.items():
        if uid == current_user_id:
            continue
        name = users_map[uid].get("full_name") or users_map[uid].get("username")
        if balance < 0 and final_split_current_user > 0:
            owes_you.append({"name": name, "amount": abs(balance)})
        elif balance > 0 and final_split_current_user < 0:
            you_owe.append({"name": name, "amount": balance})

    # -----------------------------------------------------------
    # FINAL SETTLEMENT MESSAGE
    # -----------------------------------------------------------
    if final_split_current_user > 0:
        settlement_message = f"You will RECEIVE ₹{final_split_current_user:.2f} from " + \
                             ", ".join([o["name"] for o in owes_you])
    elif final_split_current_user < 0:
        settlement_message = f"You need to PAY ₹{abs(final_split_current_user):.2f} to " + \
                             ", ".join([o["name"] for o in you_owe])
    else:
        settlement_message = "You are all settled up!"

    # -----------------------------------------------------------
    # RENDER TEMPLATE
    # -----------------------------------------------------------
    return render_template(
        "dashboard/group_detail.html",
        group=group,
        members=members,
        creator=creator,
        total_expenses=total_expenses,
        expenses_count=len(expenses),
        expenses=expenses,
        users_map=users_map,
        current_user=current_user,
        current_user_id=current_user_id,
        member_balances=member_balances,
        payment_tracker=payment_tracker,
        payment_breakdown=payment_breakdown,
        share_holding=share_holding,
        owes_you=owes_you,
        you_owe=you_owe,
        final_split=final_split_current_user,
        settlement_message=settlement_message
    )

# ------------- JOIN WITH TOKEN (email invite link) -------------
@group_bp.route("/group/join/<token>")
def join_with_token(token):
    user_session = get_session_user()
    if not user_session:
        # If not logged in, show login with message (or redirect to login page)
        return render_template("user_auth/login.html", message="Login to accept invite.", category="info")

    invite = GroupModel.verify_invite_token(token)
    if not invite:
        flash("Invite link invalid or expired.", "error")
        return redirect(url_for("group.list_groups"))

    # invited user id (ObjectId)
    invited_user_id = str(invite["user_id"])
    session_user_id = str(user_session["user_id"])

    # ensure the logged-in user is the invited user
    if invited_user_id != session_user_id:
        flash("This invite is not for your account. Please login with the invited account.", "error")
        return redirect(url_for("group.list_groups"))

    # add to group
    GroupModel.join_group(str(invite["group_id"]), invited_user_id)
    GroupModel.mark_invite_used(token)

    flash("You have joined the group.", "success")
    return redirect(url_for("group.group_details", group_id=str(invite["group_id"])))


# ------------- MANUAL JOIN (button) -------------
@group_bp.route('/<group_id>/join', methods=['POST'])
def join_group(group_id):
    user_session = get_session_user()
    if not user_session:
        return render_template("user_auth/login.html", message="Please login first.", category="error")

    GroupModel.join_group(group_id, user_session["user_id"])
    flash("You joined the group.", "success")
    return redirect(url_for("group.list_groups"))


# ------------- LEAVE -------------
@group_bp.route('/group/<group_id>/leave', methods=["GET", "POST"])
def leave_group(group_id):
    user_session = get_session_user()
    if not user_session:
        return render_template("user_auth/login.html", message="Please login first.", category="error")

    result = GroupModel.leave_group(group_id, user_session["user_id"])
    flash(result["message"], "success" if result["success"] else "error")
    return redirect(url_for("group.list_groups"))


# ------------- UPDATE -------------
@group_bp.route('/groups/<group_id>/update', methods=['GET', 'POST'])
def update_group(group_id):
    user_session = get_session_user()
    users = UserModel.get_all_users()
    current_user = UserModel.get_user_by_ID(user_session["user_id"])
    if not user_session:
        return render_template("user_auth/login.html", message="Please login first.", category="error")

    group = GroupModel.find_by_id(group_id)
    if not group:
        return redirect(url_for("group.list_groups"))

    if str(group["created_by"]) != str(user_session["user_id"]):
        return redirect(url_for("group.list_groups"))

    if request.method == 'POST':
        updated_title = request.form.get("group_title")
        updated_desc = request.form.get("group_description")
        photo_file = request.files.get("group_photo")
        print("PHOTO_FILE---------------", photo_file)

        if photo_file and photo_file.filename != "":
            group_photo = save_group_photo(photo_file)
        else:
            group_photo = group.get("group_photo")

        print("GROUP_PHOTOS---------------------", group_photo)


        update_data = {
            "group_title": updated_title,
            "group_description": updated_desc,
            "group_photo": group_photo
        }

        selected_members = request.form.getlist("members")
        selected_members = [m for m in selected_members if m.strip()]
        creator_id = str(group["created_by"])
        if creator_id not in selected_members:
            selected_members.append(creator_id)
        old_members = [str(m) for m in group["group_members"]]
        add_members = list(set(selected_members) - set(old_members))
        remove_members = [m for m in old_members if m not in selected_members and m != creator_id]

        GroupModel.update_group(
            group_id=group_id,
            updated_by=current_user['_id'],
            data=update_data,
            add_members=add_members,
            remove_members=remove_members
        )

        # When new members are added via update, send invites to those added
        for member_id in add_members:
            if str(member_id) == str(creator_id):
                continue
            user = UserModel.get_user_by_ID(member_id)
            if not user:
                continue
            token = GroupModel.create_invite_token(group_id, member_id)
            join_path = url_for("group.join_with_token", token=token)
            join_url = urllib.parse.urljoin(request.url_root, join_path)
            subject = f"You've been invited to join '{group['group_title']}'"
            html_body = f"""
                <p>Hi {user.get('username','')}</p>
                <p>You were invited to join the group <strong>{group['group_title']}</strong>.</p>
                <p><a href="{join_url}">Click here to join the group</a></p>
            """
            plain_body = f"Join {group['group_title']}: {join_url}"
            ok, err = send_email(user.get("email"), subject, html_body=html_body, plain_body=plain_body)
            if not ok:
                print("Invite send failed:", err)

        flash("Group updated and invites (if any) sent.", "success")
        return redirect(url_for("group.list_groups"))

    return render_template(
        "dashboard/edit_group.html",
        group={
            "group_id": str(group["_id"]),
            "name": group["group_title"],
            "members": [str(m) for m in group["group_members"]],
            "description": group.get("group_description", ""),
            "group_photo": group.get("group_photo")
        },
        users=[{
            "user_id": str(u["_id"]),
            "username": u.get("username"),
            "email": u.get("email")
        } for u in users],
        current_user_id=str(current_user["_id"]),
        current_user=current_user
    )

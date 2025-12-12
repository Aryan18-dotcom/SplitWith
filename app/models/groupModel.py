from . import GetDB
from bson import ObjectId
from datetime import datetime, timedelta
import uuid

INVITE_COLLECTION = "group_invites"
INVITE_TTL_DAYS = 7  # token lifetime


def to_object_id(x):
    """Convert id to ObjectId safely."""
    if isinstance(x, ObjectId):
        return x
    if isinstance(x, dict) and "user_id" in x:
        x = x["user_id"]
    if isinstance(x, dict) and "_id" in x:
        x = x["_id"]
    if x is None:
        return None
    return ObjectId(str(x))


class GroupModel:

    @staticmethod
    def collection():
        return mongo.db.groups

    # -------------------------
    # CREATE GROUP
    # -------------------------
    @staticmethod
    def create_group(created_by, title, description, group_photo=None, members=None, is_personal=False):
        if members is None:
            members = []

        # Convert creator ID
        created_by_oid = to_object_id(created_by)

        # Ensure creator is included
        if str(created_by) not in members:
            members.append(str(created_by))

        # Convert all members safely
        valid_member_ids = [to_object_id(m) for m in members if m]

        group_data = {
            "created_by": created_by_oid,
            "group_title": title,
            "group_description": description,
            "group_photo": group_photo,
            "group_members": valid_member_ids,
            "total_balance": 0,
            "created_at": datetime.utcnow(),
            "is_personal": is_personal
        }

        res = GroupModel.collection().insert_one(group_data)
        return str(res.inserted_id)

    # -------------------------
    # FIND BY ID
    # -------------------------
    @staticmethod
    def find_by_id(group_id):
        return GroupModel.collection().find_one({"_id": to_object_id(group_id)})

    # -------------------------
    # JOIN GROUP
    # -------------------------
    @staticmethod
    def join_group(group_id, user_id):
        return GroupModel.collection().update_one(
            {"_id": to_object_id(group_id)},
            {"$addToSet": {"group_members": to_object_id(user_id)}}
        )

    # -------------------------
    # LEAVE GROUP
    # -------------------------
    @staticmethod
    def leave_group(group_id, user_id):
        group = GroupModel.find_by_id(group_id)
        if not group:
            return {"success": False, "message": "Group not found."}

        if str(group["created_by"]) == str(user_id):
            return {"success": False, "message": "Group creator cannot leave the group."}

        GroupModel.collection().update_one(
            {"_id": to_object_id(group_id)},
            {"$pull": {"group_members": to_object_id(user_id)}}
        )
        return {"success": True, "message": "Left group successfully."}

    # -------------------------
    # UPDATE GROUP
    # -------------------------
    @staticmethod
    def update_group(group_id, updated_by, data, add_members=None, remove_members=None):

        group = GroupModel.find_by_id(group_id)
        if not group:
            return {"success": False, "message": "Group not found."}

        if str(group["created_by"]) != str(updated_by):
            return {"success": False, "message": "Not authorized."}

        update_fields = {}

        if data.get("group_title") is not None:
            update_fields["group_title"] = data["group_title"]

        if data.get("group_description") is not None:
            update_fields["group_description"] = data["group_description"]

        if data.get("group_photo") is not None:
            update_fields["group_photo"] = data["group_photo"]

        if update_fields:
            GroupModel.collection().update_one(
                {"_id": to_object_id(group_id)},
                {"$set": update_fields}
            )

        # Add members
        if add_members:
            oids = [to_object_id(m) for m in add_members]
            GroupModel.collection().update_one(
                {"_id": to_object_id(group_id)},
                {"$addToSet": {"group_members": {"$each": oids}}}
            )

        # Remove members (except creator)
        if remove_members:
            safe_remove = [m for m in remove_members if str(m) != str(group["created_by"])]
            if safe_remove:
                oids = [to_object_id(m) for m in safe_remove]
                GroupModel.collection().update_one(
                    {"_id": to_object_id(group_id)},
                    {"$pull": {"group_members": {"$in": oids}}}
                )

        return {"success": True, "message": "Group updated successfully."}

    # -------------------------
    # GET USER GROUPS
    # -------------------------
    @staticmethod
    def get_user_groups(user_id):
        # If a dictionary is passed, treat it as a custom query
        if isinstance(user_id, dict):
            return list(GroupModel.collection().find(user_id))

        # Otherwise, treat it as normal user_id
        uid = to_object_id(user_id)
        return list(GroupModel.collection().find({"group_members": uid}))


    # -------------------------
    # GET GROUPS WITH USERS
    # -------------------------
    @staticmethod
    def get_user_groups_with_users(user_id):
        db = GetDB._get_db()
        uid = to_object_id(user_id)

        groups = list(db.groups.find({"group_members": uid}))

        # Collect all user ids
        user_ids = {member for g in groups for member in g.get("group_members", [])}

        users_map = {
            str(u["_id"]): u
            for u in db.users.find({"_id": {"$in": list(user_ids)}})
        }

        for g in groups:
            g["members_full"] = [
                users_map.get(str(uid)) for uid in g.get("group_members", [])
            ]

        return groups

    # -------------------------
    # INVITE SYSTEM
    # -------------------------
    @staticmethod
    def _invite_collection():
        db = GetDB._get_db()
        return getattr(db, INVITE_COLLECTION)

    @staticmethod
    def create_invite_token(group_id, user_id, ttl_days=INVITE_TTL_DAYS):
        token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=ttl_days)

        invite_doc = {
            "group_id": to_object_id(group_id),
            "user_id": to_object_id(user_id),
            "token": token,
            "used": False,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at
        }

        GroupModel._invite_collection().insert_one(invite_doc)
        return token

    @staticmethod
    def verify_invite_token(token):
        doc = GroupModel._invite_collection().find_one(
            {"token": token, "used": False}
        )
        if not doc:
            return None
        if doc.get("expires_at") and datetime.utcnow() > doc["expires_at"]:
            return None
        return doc

    @staticmethod
    def mark_invite_used(token):
        return GroupModel._invite_collection().update_one(
            {"token": token}, {"$set": {"used": True}}
        )


    # -------------------------
    # AUTO UPDATE TOTAL BALANCE
    # -------------------------
    @staticmethod
    def update_group_total_balance(group_id):
        """Recalculate and update the total balance of a group based on its expenses."""
        db = GetDB._get_db()

        pipeline = [
            {"$match": {"group_id": to_object_id(group_id)}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]

        result = list(db.expenses.aggregate(pipeline))
        total_balance = result[0]["total"] if result else 0

        GroupModel.collection().update_one(
            {"_id": to_object_id(group_id)},
            {"$set": {"total_balance": total_balance}}
        )

        return total_balance

    @staticmethod
    def get_all_groups():
        return list(GroupModel.collection().find())
    
    @staticmethod
    def get_group_members(group_id):
        group = GroupModel.find_by_id(group_id)
        if not group:
            return []
        return group.get("group_members", [])
    
    @staticmethod
    def get_group_by_id(group_id):
        return GroupModel.find_by_id(group_id)
    
    @staticmethod
    def add_total_balance(group_id, amount):
        return GroupModel.collection().update_one(
            {"_id": to_object_id(group_id)},
            {"$inc": {"total_balance": float(amount)}}
        )

    @staticmethod
    def get_personal_group(user_ids_sorted, group_name):
        db = GetDB._get_db()
        user_ids_obj = [ObjectId(uid) if isinstance(uid, str) else uid for uid in user_ids_sorted]

        return db.groups.find_one({
            "is_personal": True,
            "group_title": group_name,
            "group_members": {"$all": user_ids_obj, "$size": len(user_ids_obj)}
        })

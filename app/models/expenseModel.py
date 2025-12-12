# expenseModel.py
from bson.objectid import ObjectId
from datetime import datetime
from ..extensions import mongo

class ExpenseModel:

    @staticmethod
    def collection():
        return mongo.db.expenses


    @staticmethod
    def create_expense(data):
        doc = {
            "title": data.get("title"),
            "amount": float(data.get("amount")),
            "group_id": data.get("group_id"),
            "created_by": data.get("created_by"),
            "split_type": data.get("split_type"),
            "split_with": data.get("split_with", []),            # list of user ids (strings)
            "custom_payments": data.get("custom_payments", {}),  # { user_id: amount_paid }
            "custom_shares": data.get("custom_shares", {}),      # { user_id: share_amount_or_percent }
            "final_split": data.get("final_split", {}),          # { user_id: { should_pay, paid, net_balance } }
            "description": data.get("description"),
            "created_at": datetime.utcnow(),
        }
        return ExpenseModel.collection().insert_one(doc)

    @staticmethod
    def get_expenses_for_user(user_id):
        if not user_id:
            return []

        expenses = ExpenseModel.collection().find({
            "$or": [
                {"created_by": user_id},
                {"split_with": {"$in": [user_id]}}
            ]
        }).sort("created_at", -1)

        return list(expenses) if expenses else []


    @staticmethod
    def get_by_id(expense_id):
        return ExpenseModel.collection().find_one({"_id": ObjectId(expense_id)})

    @staticmethod
    def update_expense(expense_id, data):
        return ExpenseModel.collection().update_one(
            {"_id": ObjectId(expense_id)},
            {"$set": data}
        )

    @staticmethod
    def delete_expense(expense_id):
        return ExpenseModel.collection().delete_one({"_id": ObjectId(expense_id)})

    # ---------------- CORE: Calculate split ----------------
    @staticmethod
    def calculate_split(amount, members, split_type, payer, custom_shares=None, custom_payments=None):
        """
        Calculates final per-user expense split in a clean and industry-level reliable way.
        """

        amount = float(amount)
        members = [str(m) for m in members]
        n = len(members)
        if n == 0:
            return {}

        custom_shares = {str(k): float(v) for k, v in (custom_shares or {}).items()}
        custom_payments = {str(k): float(v) for k, v in (custom_payments or {}).items()}

        # Initialize result dict
        result = {
            m: {"should_pay": 0.0, "paid": 0.0, "net_balance": 0.0}
            for m in members
        }

        # Set initial paid amounts (if provided)
        for m in members:
            result[m]["paid"] = round(custom_payments.get(m, 0.0), 2)

        payer = str(payer)

        # -------------------------------------------------------
        # 1) EQUAL SPLIT
        # -------------------------------------------------------
        if split_type == "equal":
            share = round(amount / n, 2)
            for m in members:
                result[m]["should_pay"] = share

            # payer should be marked as paid full if nobody set it
            if result[payer]["paid"] == 0:
                result[payer]["paid"] = amount

        # -------------------------------------------------------
        # 2) PAID BY ME
        # -------------------------------------------------------
        elif split_type == "paid_by_me":
            if n == 1:
                # Only payer exists
                result[payer]["should_pay"] = 0
                result[payer]["paid"] = amount
            else:
                share = round(amount / (n - 1), 2)
                for m in members:
                    if m == payer:
                        result[m]["should_pay"] = 0
                        result[m]["paid"] = amount
                    else:
                        result[m]["should_pay"] = share

        # -------------------------------------------------------
        # 3) PAID BY OTHER
        # -------------------------------------------------------
        elif split_type == "paid_by_other":
            if n == 1:
                result[payer]["should_pay"] = 0
                result[payer]["paid"] = amount
            else:
                share = round(amount / (n - 1), 2)
                for m in members:
                    if m == payer:
                        result[m]["should_pay"] = 0
                        result[m]["paid"] = amount
                    else:
                        result[m]["should_pay"] = share

        # -------------------------------------------------------
        # 4) CUSTOM SPLIT
        # -------------------------------------------------------
        elif split_type == "custom":
            # Sum of provided shares
            provided_sum = round(sum(custom_shares.get(m, 0.0) for m in members), 2)

            # Case A: shares match amount → use directly
            if abs(provided_sum - amount) <= 0.01 and provided_sum > 0:
                for m in members:
                    result[m]["should_pay"] = round(custom_shares.get(m, 0.0), 2)

            # Case B: proportions need normalization
            elif provided_sum > 0:
                for m in members:
                    proportional = (custom_shares.get(m, 0.0) / provided_sum) * amount
                    result[m]["should_pay"] = round(proportional, 2)

            # Case C: nothing provided → fallback to equal
            else:
                share = round(amount / n, 2)
                for m in members:
                    result[m]["should_pay"] = share

            # VERY IMPORTANT:
            # Ensure payer "paid" full amount unless user explicitly overrode it
            if sum(result[m]["paid"] for m in members) == 0:
                result[payer]["paid"] = amount

        # -------------------------------------------------------
        # 5) FINAL CALCULATION
        # -------------------------------------------------------
        for m in members:
            paid = result[m]["paid"]
            should = result[m]["should_pay"]
            result[m]["net_balance"] = round(paid - should, 2)

        return result


    @staticmethod
    def get_expenses_for_group(group_id):
        if not group_id:
            return []

        expenses = ExpenseModel.collection().find({
            "group_id": group_id
        }).sort("created_at", -1)

        return list(expenses) if expenses else []
    
    @staticmethod
    def get_most_active_groups_for_user(user_id, limit=10):
        """
        Count expenses per group where user is either creator or in split_with.
        Returns list of groups sorted by activity.
        """

        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"created_by": user_id},
                        {"split_with": {"$in": [user_id]}}
                    ]
                }
            },
            {
                "$group": {
                    "_id": "$group_id",
                    "expense_count": {"$sum": 1}
                }
            },
            {"$sort": {"expense_count": -1}},
            {"$limit": limit}
        ]

        data = list(ExpenseModel.collection().aggregate(pipeline))

        # Fetch full group details
        for g in data:
            group = ExpenseModel.collection().find_one({"_id": ObjectId(g["_id"])})
            g["group"] = group

        return data


    # -------------------------------------------
    # 2️⃣ MONTHLY EXPENSES FOR A USER
    # -------------------------------------------
    @staticmethod
    def get_monthly_expenses_for_user(user_id):
        """
        Returns monthly grouped expense totals for the user in format:
        [
            { "_id": { "year": 2025, "month": 1 }, "total_amount": 200 },
            { "_id": { "year": 2025, "month": 2 }, "total_amount": 340 }
        ]
        """
        pipeline = [
            {
                "$match": {
                    "created_by": user_id
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$created_at"},
                        "month": {"$month": "$created_at"}
                    },
                    "total_amount": {"$sum": "$amount"}
                }
            },
            {
                "$sort": {
                    "_id.year": 1,
                    "_id.month": 1
                }
            }
        ]

        return list(ExpenseModel.collection().aggregate(pipeline))


    # -------------------------------------------
    # 3️⃣ TOTAL OWED TO USER (what others owe me)
    # -------------------------------------------
    @staticmethod
    def get_total_owed_to_user(user_id):
        """
        Sum of (should_pay - paid) for users OTHER than created_by,
        but only from final_split field.
        """

        pipeline = [
            {
                "$match": {
                    "created_by": user_id
                }
            },
            {
                "$project": {
                    "final_split": 1
                }
            }
        ]

        expenses = ExpenseModel.collection().aggregate(pipeline)

        total = 0

        for exp in expenses:
            fs = exp.get("final_split", {})
            for uid, bal in fs.items():
                if uid != user_id:   # others owe me
                    net = bal.get("net_balance", 0)
                    if net < 0:      # negative means they owe
                        total += abs(net)

        return round(total, 2)


    # -------------------------------------------
    # 4️⃣ TOTAL USER OWES (what I owe others)
    # -------------------------------------------
    @staticmethod
    def get_total_user_owes(user_id):
        """
        Sum of negative net_balance for the user across all expenses.
        """

        pipeline = [
            {
                "$match": {
                    "split_with": {"$in": [user_id]}
                }
            },
            {
                "$project": {
                    "final_split": 1
                }
            }
        ]

        expenses = ExpenseModel.collection().aggregate(pipeline)

        total = 0

        for exp in expenses:
            fs = exp.get("final_split", {})
            my_data = fs.get(user_id)

            if my_data:
                net = my_data.get("net_balance", 0)
                if net < 0:          # I owe
                    total += abs(net)

        return round(total, 2)

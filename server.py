"""
Bank Security System - Web Server
Flask API backend serving the web UI.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, send_from_directory, session
from functools import wraps
import db_manager
from auth import hash_password, verify_password

app = Flask(__name__, static_folder="static")
app.secret_key = "bank_security_system_secret_key_2024"


# ─────────────────────────────────────────────
# Auth Decorator
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return jsonify({"error": "Not authenticated"}), 401
            if session["user"]["role"] not in roles:
                return jsonify({"error": "Access denied"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─────────────────────────────────────────────
# Static Files
# ─────────────────────────────────────────────

@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


# ─────────────────────────────────────────────
# AUTH API
# ─────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    username = data.get("username", "")
    password = data.get("password", "")

    user = db_manager.get_user_by_username(username)
    if not user:
        return jsonify({"error": "User not found"}), 401

    if not user["is_active"]:
        return jsonify({"error": "Account deactivated. Contact your manager."}), 401

    if not verify_password(password, user["password_hash"]):
        db_manager.add_system_log("LOGIN_FAILED", user["user_id"], f"Failed login for '{username}'")
        return jsonify({"error": "Incorrect password"}), 401

    # Store in session
    session["user"] = {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
    }

    db_manager.add_system_log("LOGIN_SUCCESS", user["user_id"], f"User '{username}' logged in (web)")
    db_manager.add_audit_log("LOGIN", username, details=f"Role: {user['role']} (web)")

    return jsonify({
        "success": True,
        "user": session["user"],
    })


@app.route("/api/logout", methods=["POST"])
@login_required
def api_logout():
    user = session["user"]
    db_manager.add_system_log("LOGOUT", user["user_id"], f"User '{user['username']}' logged out (web)")
    session.pop("user", None)
    return jsonify({"success": True})


@app.route("/api/me")
@login_required
def api_me():
    return jsonify(session["user"])


# ─────────────────────────────────────────────
# CUSTOMER API
# ─────────────────────────────────────────────

@app.route("/api/accounts")
@login_required
def api_accounts():
    user = session["user"]
    if user["role"] in ("accountant", "manager"):
        accounts = db_manager.get_all_accounts()
    else:
        accounts = db_manager.get_accounts_by_user(user["user_id"])
    return jsonify(accounts)


@app.route("/api/accounts/<int:account_id>")
@login_required
def api_account_detail(account_id):
    account = db_manager.get_account_by_id(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    user = session["user"]
    if user["role"] == "customer" and account["user_id"] != user["user_id"]:
        return jsonify({"error": "Access denied"}), 403

    return jsonify(account)


@app.route("/api/accounts/<int:account_id>/transactions")
@login_required
def api_account_transactions(account_id):
    account = db_manager.get_account_by_id(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    user = session["user"]
    if user["role"] == "customer" and account["user_id"] != user["user_id"]:
        return jsonify({"error": "Access denied"}), 403

    txns = db_manager.get_transactions_by_account(account_id, limit=50)
    return jsonify(txns)


@app.route("/api/deposit", methods=["POST"])
@role_required("customer", "manager")
def api_deposit():
    data = request.json
    account_id = data.get("account_id")
    amount = data.get("amount", 0)

    account = db_manager.get_account_by_id(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    user = session["user"]
    if user["role"] == "customer" and account["user_id"] != user["user_id"]:
        return jsonify({"error": "Access denied"}), 403

    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400

    new_balance = account["balance"] + amount
    db_manager.update_balance(account_id, new_balance)
    db_manager.add_transaction(account_id, "deposit", amount, f"Deposit by {user['username']} (web)")
    db_manager.add_audit_log("DEPOSIT", user["username"], account_id, f"₹{amount:,.2f} deposited (web)")

    return jsonify({"success": True, "new_balance": new_balance})


@app.route("/api/withdraw", methods=["POST"])
@role_required("customer", "manager")
def api_withdraw():
    data = request.json
    account_id = data.get("account_id")
    amount = data.get("amount", 0)

    account = db_manager.get_account_by_id(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    user = session["user"]
    if user["role"] == "customer" and account["user_id"] != user["user_id"]:
        return jsonify({"error": "Access denied"}), 403

    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400

    if amount > account["balance"]:
        return jsonify({"error": "Insufficient balance"}), 400

    if amount >= 5000:
        db_manager.create_request(account_id, "large_withdrawal", amount, f"Requested by {user['username']} (web)")
        db_manager.add_audit_log("WITHDRAWAL_REQUEST", user["username"], account_id, f"₹{amount:,.2f} — pending (web)")
        return jsonify({"success": True, "pending": True, "message": "Large withdrawal requires accountant approval. Request submitted."})

    new_balance = account["balance"] - amount
    db_manager.update_balance(account_id, new_balance)
    db_manager.add_transaction(account_id, "withdrawal", amount, f"Withdrawal by {user['username']} (web)")
    db_manager.add_audit_log("WITHDRAWAL", user["username"], account_id, f"₹{amount:,.2f} withdrawn (web)")

    return jsonify({"success": True, "new_balance": new_balance})


@app.route("/api/transfer", methods=["POST"])
@role_required("customer", "manager")
def api_transfer():
    data = request.json
    src_id = data.get("from_account_id")
    dst_id = data.get("to_account_id")
    amount = data.get("amount", 0)

    src = db_manager.get_account_by_id(src_id)
    dst = db_manager.get_account_by_id(dst_id)

    if not src:
        return jsonify({"error": "Source account not found"}), 404
    if not dst:
        return jsonify({"error": "Destination account not found"}), 404

    user = session["user"]
    if user["role"] == "customer" and src["user_id"] != user["user_id"]:
        return jsonify({"error": "Access denied"}), 403

    if src_id == dst_id:
        return jsonify({"error": "Cannot transfer to same account"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400
    if amount > src["balance"]:
        return jsonify({"error": "Insufficient balance"}), 400

    if amount >= 5000:
        db_manager.create_request(src_id, "large_transfer", amount, f"Transfer to #{dst_id} by {user['username']} (web)")
        db_manager.add_audit_log("TRANSFER_REQUEST", user["username"], src_id, f"₹{amount:,.2f} to #{dst_id} — pending (web)")
        return jsonify({"success": True, "pending": True, "message": "Large transfer requires approval. Request submitted."})

    db_manager.update_balance(src_id, src["balance"] - amount)
    db_manager.update_balance(dst_id, dst["balance"] + amount)
    db_manager.add_transaction(src_id, "transfer", amount, f"Transfer to #{dst_id} (web)", "completed", dst_id)
    db_manager.add_transaction(dst_id, "deposit", amount, f"Transfer from #{src_id} (web)", "completed", src_id)
    db_manager.add_audit_log("TRANSFER", user["username"], src_id, f"₹{amount:,.2f} → #{dst_id} (web)")

    return jsonify({"success": True, "new_balance": src["balance"] - amount})


# ─────────────────────────────────────────────
# ACCOUNTANT API
# ─────────────────────────────────────────────

@app.route("/api/requests")
@role_required("accountant", "manager")
def api_requests():
    return jsonify(db_manager.get_pending_requests())


@app.route("/api/requests/all")
@role_required("accountant", "manager")
def api_all_requests():
    return jsonify(db_manager.get_all_requests())


@app.route("/api/requests/<int:request_id>/process", methods=["POST"])
@role_required("accountant", "manager")
def api_process_request(request_id):
    data = request.json
    action = data.get("action")  # approve or reject
    user = session["user"]

    requests_list = db_manager.get_pending_requests()
    target = None
    for r in requests_list:
        if r["request_id"] == request_id:
            target = r
            break

    if not target:
        return jsonify({"error": "Request not found or already processed"}), 404

    if action == "approve":
        db_manager.update_request_status(request_id, "approved", user["username"])
        account = db_manager.get_account_by_id(target["account_id"])

        if account:
            if target["request_type"] in ("large_withdrawal", "large_transfer"):
                new_bal = account["balance"] - target["amount"]
                if new_bal >= 0:
                    db_manager.update_balance(target["account_id"], new_bal)
                    txn_type = "withdrawal" if "withdrawal" in target["request_type"] else "transfer"
                    db_manager.add_transaction(target["account_id"], txn_type, target["amount"],
                                               f"Approved (Req #{request_id}) by {user['username']}")
                else:
                    return jsonify({"error": "Insufficient balance to execute"}), 400
            elif target["request_type"] == "account_close":
                db_manager.close_account(target["account_id"])

        db_manager.add_audit_log("REQUEST_APPROVED", user["username"], target["account_id"],
                                 f"Req #{request_id} approved (web)")
        return jsonify({"success": True, "message": f"Request #{request_id} approved"})

    elif action == "reject":
        db_manager.update_request_status(request_id, "rejected", user["username"])
        db_manager.add_audit_log("REQUEST_REJECTED", user["username"], target["account_id"],
                                 f"Req #{request_id} rejected (web)")
        return jsonify({"success": True, "message": f"Request #{request_id} rejected"})

    return jsonify({"error": "Invalid action"}), 400


@app.route("/api/accounts/create", methods=["POST"])
@role_required("accountant", "manager")
def api_create_account():
    data = request.json
    user = session["user"]

    acc_id = db_manager.create_account(
        data["customer_name"], data["email"], data["phone"],
        data.get("balance", 0), data.get("account_type", "savings"),
        data["user_id"]
    )
    db_manager.add_audit_log("ACCOUNT_CREATED", user["username"], acc_id,
                             f"{data.get('account_type', 'savings')} for {data['customer_name']} (web)")
    return jsonify({"success": True, "account_id": acc_id})


@app.route("/api/audit-logs")
@role_required("accountant", "manager")
def api_audit_logs():
    return jsonify(db_manager.get_audit_logs(50))


@app.route("/api/transactions/all")
@role_required("accountant", "manager")
def api_all_transactions():
    return jsonify(db_manager.get_all_transactions(100))


# ─────────────────────────────────────────────
# MANAGER API
# ─────────────────────────────────────────────

@app.route("/api/users")
@role_required("manager")
def api_users():
    return jsonify(db_manager.get_all_users())


@app.route("/api/users/create", methods=["POST"])
@role_required("manager")
def api_create_user():
    data = request.json
    user = session["user"]

    if db_manager.get_user_by_username(data["username"]):
        return jsonify({"error": "Username already exists"}), 400

    uid = db_manager.create_user(data["username"], hash_password(data["password"]), data["role"], data["full_name"])

    # Auto-create a savings account for new customers
    if data["role"] == "customer":
        acc_id = db_manager.create_account(
            customer_name=data["full_name"],
            email=f"{data['username']}@bank.com",
            phone="0000000000",
            balance=0.0,
            account_type="savings",
            user_id=uid
        )
        db_manager.add_system_log("ACCOUNT_CREATED", user["user_id"],
            f"Auto-created savings account #{acc_id} for new customer '{data['username']}' (web)")

    db_manager.add_system_log("USER_CREATED", user["user_id"], f"Created {data['role']}: {data['username']} (web)")
    return jsonify({"success": True, "user_id": uid})


@app.route("/api/users/<int:user_id>/toggle", methods=["POST"])
@role_required("manager")
def api_toggle_user(user_id):
    user = session["user"]
    if user_id == user["user_id"]:
        return jsonify({"error": "Cannot toggle your own account"}), 400

    users = db_manager.get_all_users()
    target = None
    for u in users:
        if u["user_id"] == user_id:
            target = u
            break
    if not target:
        return jsonify({"error": "User not found"}), 404

    new_status = not target["is_active"]
    db_manager.toggle_user_active(user_id, new_status)
    status_text = "activated" if new_status else "deactivated"
    db_manager.add_system_log("USER_TOGGLED", user["user_id"], f"{target['username']} {status_text} (web)")
    return jsonify({"success": True, "is_active": new_status})


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@role_required("manager")
def api_delete_user(user_id):
    user = session["user"]
    if user_id == user["user_id"]:
        return jsonify({"error": "Cannot delete your own account"}), 400

    # Get target user info before deletion
    users = db_manager.get_all_users()
    target = None
    for u in users:
        if u["user_id"] == user_id:
            target = u
            break
    if not target:
        return jsonify({"error": "User not found"}), 404

    db_manager.delete_user(user_id)
    db_manager.add_system_log("USER_DELETED", user["user_id"], f"Deleted user '{target['username']}' (role: {target['role']}) (web)")
    db_manager.add_audit_log("USER_DELETED", user["username"], details=f"Deleted {target['role']}: {target['username']} ({target['full_name']}) (web)")
    return jsonify({"success": True})


@app.route("/api/system-logs")
@role_required("manager")
def api_system_logs():
    return jsonify(db_manager.get_system_logs(50))


@app.route("/api/report")
@role_required("manager")
def api_report():
    user = session["user"]
    report = {
        "total_balance": db_manager.get_total_balance(),
        "total_deposits": db_manager.get_total_deposits(),
        "total_withdrawals": db_manager.get_total_withdrawals(),
        "account_count": db_manager.get_account_count(),
        "user_count": db_manager.get_user_count(),
        "pending_requests": len(db_manager.get_pending_requests()),
        "branches": db_manager.get_branch_info(),
    }
    db_manager.add_system_log("REPORT_GENERATED", user["user_id"], "Bank summary report (web)")
    return jsonify(report)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    db_manager.init_all_databases()
    print("\n🏦 Bank Security System — Web UI")
    print("   http://localhost:5001\n")
    app.run(debug=True, port=5001)

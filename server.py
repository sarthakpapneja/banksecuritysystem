"""
Bank Security System - Web Server
Flask API backend serving the web UI.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, send_from_directory, session, g
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

    if user.get("is_locked"):
        return jsonify({"error": "Account locked due to multiple failed attempts. Contact your manager or accountant to unlock."}), 401

    if not verify_password(password, user["password_hash"]):
        attempts = db_manager.increment_failed_attempts(user["user_id"])
        if attempts >= 3:
            db_manager.lock_user(user["user_id"])
            db_manager.add_system_log("ACCOUNT_LOCKED", user["user_id"], f"Account locked after {attempts} failed attempts")
            return jsonify({"error": "Account locked due to 3 failed attempts. Contact your manager or accountant to unlock."}), 401
        remaining = 3 - attempts
        db_manager.add_system_log("LOGIN_FAILED", user["user_id"], f"Failed login for '{username}' (attempt {attempts})")
        return jsonify({"error": f"Incorrect password. {remaining} attempt(s) remaining before lockout."}), 401

    # Successful login — reset failed attempts
    db_manager.reset_failed_attempts(user["user_id"])

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


@app.route("/api/accounts/lookup/<int:account_id>")
@login_required
def api_account_lookup(account_id):
    """
    Public lookup for account existence and recipient name.
    Does not expose balance or other sensitive details.
    """
    account = db_manager.get_account_by_id(account_id)
    if not account or not account["is_active"]:
        return jsonify({"error": "Account not found"}), 404
    
    return jsonify({
        "account_id": account["account_id"],
        "customer_name": account["customer_name"]
    })


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

    category = data.get("category", "Deposit")
    
    new_balance = account["balance"] + amount
    db_manager.update_balance(account_id, new_balance)
    db_manager.add_transaction(account_id, "deposit", amount, f"Deposit by {user['username']} (web)", category=category)
    db_manager.add_audit_log("DEPOSIT", user["username"], account_id, f"₹{amount:,.2f} deposited (web)")

    # Notify user
    db_manager.add_notification(account["user_id"], f"₹{amount:,.2f} has been deposited into your account #{account_id}. New balance: ₹{new_balance:,.2f}", "success")

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
        db_manager.create_security_alert(user["user_id"], f"A large withdrawal of ₹{amount:,.2f} has been requested and requires accountant approval.", "warning")
        db_manager.notify_staff(f"New large withdrawal request of ₹{amount:,.2f} from Account #{account_id}.")
        return jsonify({"success": True, "pending": True, "message": "Large withdrawal requires accountant approval. Request submitted."})

    category = data.get("category", "Withdrawal")

    new_balance = account["balance"] - amount
    db_manager.update_balance(account_id, new_balance)
    db_manager.add_transaction(account_id, "withdrawal", amount, f"Withdrawal by {user['username']} (web)", category=category)
    db_manager.add_audit_log("WITHDRAWAL", user["username"], account_id, f"₹{amount:,.2f} withdrawn (web)")

    # Notify user
    db_manager.add_notification(account["user_id"], f"₹{amount:,.2f} has been withdrawn from your account #{account_id}. Remaining balance: ₹{new_balance:,.2f}", "warning")
    if new_balance < 1000:
        db_manager.add_notification(account["user_id"], f"Low balance alert! Your account #{account_id} balance is ₹{new_balance:,.2f}.", "error")

    return jsonify({"success": True, "new_balance": new_balance})


@app.route("/api/transfer", methods=["POST"])
@role_required("customer", "manager")
def api_transfer():
    data = request.json
    src_id = data.get("src_id")
    dst_id = data.get("dst_id")
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
        db_manager.create_security_alert(user["user_id"], f"A large transfer of ₹{amount:,.2f} to account #{dst_id} has been requested and is pending approval.", "warning")
        db_manager.notify_staff(f"New large transfer request of ₹{amount:,.2f} from Account #{src_id} to Account #{dst_id}.")
        return jsonify({"success": True, "pending": True, "message": "Large transfer requires approval. Request submitted."})

    category = data.get("category", "Transfer")

    db_manager.update_balance(src_id, src["balance"] - amount)
    db_manager.update_balance(dst_id, dst["balance"] + amount)
    db_manager.add_transaction(src_id, "transfer", amount, f"Transfer to #{dst_id} (web)", "completed", dst_id, category=category)
    db_manager.add_transaction(dst_id, "deposit", amount, f"Transfer from #{src_id} (web)", "completed", src_id, category=category)
    db_manager.add_audit_log("TRANSFER", user["username"], src_id, f"₹{amount:,.2f} → #{dst_id} (web)")

    # Notify both participants
    db_manager.add_notification(src["user_id"], f"Sent ₹{amount:,.2f} to Account #{dst_id}.", "warning")
    db_manager.add_notification(dst["user_id"], f"Received ₹{amount:,.2f} from Account #{src_id}.", "success")

    return jsonify({"success": True, "new_balance": src["balance"] - amount})


# ─────────────────────────────────────────────
# SECURITY ALERTS API
# ─────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
@login_required
def api_get_alerts():
    return jsonify(db_manager.get_unread_alerts(session["user"]["user_id"]))


@app.route("/api/alerts/<int:alert_id>/read", methods=["POST"])
@login_required
def api_read_alert(alert_id):
    db_manager.mark_alert_read(session["user"]["user_id"], alert_id)
    return jsonify({"success": True})


# ─────────────────────────────────────────────
# ACCOUNTANT API
# ─────────────────────────────────────────────

@app.route("/api/requests")
@role_required("accountant", "manager")
def api_requests():
    user = session["user"]
    if user["role"] == "manager":
        # Managers see all non-loan requests pending manager approval
        all_reqs = db_manager.get_pending_requests()
        # The new get_pending_requests and get_pending_manager_requests already exclude loans.
        # But wait, a manager is supposed to approve all accountants' approved requests? 
        # For non-loans, currently only accountants approve them completely (1 step).
        # Ah, the original code had:
        return jsonify(db_manager.get_pending_requests())
    else:
        # Accountants see all requests pending accountant approval, excluding loans
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
        account = db_manager.get_account_by_id(target["account_id"])

        db_manager.update_request_status(request_id, "approved", user["username"])

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
            elif target["request_type"] == "credit_card":
                # Create credit card with 15% APR as default
                c_id = db_manager.create_credit_card(target["account_id"], target["amount"], 15.0)
                db_manager.create_security_alert(account["user_id"], f"Your credit card application for a limit of ₹{target['amount']:,.2f} has been approved!", "success")

        db_manager.add_audit_log("REQUEST_APPROVED", user["username"], target["account_id"],
                                 f"Req #{request_id} ({target['request_type']}) approved (web)")
        return jsonify({"success": True, "message": f"Request #{request_id} approved"})

    elif action == "reject":
        db_manager.update_request_status(request_id, "rejected", user["username"])
        db_manager.add_audit_log("REQUEST_REJECTED", user["username"], target["account_id"], f"Req #{request_id} rejected (web)")
        return jsonify({"success": True, "message": f"Request #{request_id} rejected"})

    return jsonify({"error": "Invalid action"}), 400

# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# TRANSACTIONS API


@app.route("/api/active_loans", methods=["GET"])
@role_required("customer")
def api_active_loans():
    user = session["user"]
    accounts = db_manager.get_accounts_by_user(user["user_id"])
    all_active_loans = []
    for acc in accounts:
        loans = db_manager.get_active_loans_by_account(acc["account_id"])
        all_active_loans.extend(loans)
    return jsonify(all_active_loans)


@app.route("/api/loan/pay", methods=["POST"])
@role_required("customer")
def api_loan_pay():
    data = request.json
    loan_id = data.get("loan_id")
    
    loan = db_manager.get_loan_by_id(loan_id)
    if not loan or loan["status"] != "active":
        return jsonify({"error": "Loan not found or not currently active"}), 404
        
    total_cost = loan["emi_amount"] * loan["tenure_months"]
    remaining_balance = total_cost - loan["total_paid"]
    
    if remaining_balance <= 0.01:
        return jsonify({"error": "Loan is already fully paid off"}), 400

    account = db_manager.get_account_by_id(loan["account_id"])
    if account["user_id"] != session["user"]["user_id"]:
        return jsonify({"error": "Access denied"}), 403

    emi_amount = min(loan["emi_amount"], remaining_balance)

    if account["balance"] < emi_amount:
        return jsonify({"error": f"Insufficient balance in account #{account['account_id']} to pay EMI of ₹{emi_amount:,.2f}"}), 400

    # Deduct EMI and reduce loan balance
    db_manager.update_balance(account["account_id"], account["balance"] - emi_amount)
    db_manager.add_transaction(account["account_id"], "withdrawal", emi_amount, f"EMI Payment for Loan #{loan_id}")
    db_manager.record_loan_emi_payment(loan_id, emi_amount)

    return jsonify({"success": True, "message": f"Successfully paid EMI of ₹{emi_amount:,.2f}"})


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


@app.route("/api/audit")
@login_required
def api_user_audit():
    user = session["user"]
    return jsonify(db_manager.get_audit_logs_by_user(user["username"]))


@app.route("/api/audit-log")
@role_required("accountant", "manager")
def api_audit_logs():
    return jsonify(db_manager.get_audit_logs(100))


@app.route("/api/transactions/all")
@role_required("accountant", "manager")
def api_all_transactions():
    return jsonify(db_manager.get_all_transactions(100))

@app.route("/api/transactions", methods=["GET"])
@login_required
def api_get_transactions_filtered():
    user = session["user"]
    category = request.args.get("category")
    txn_type = request.args.get("txn_type")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # If accountant/manager and no specific user constraint is requested, fetch all
    user_id_filter = None
    if user["role"] == "customer":
        user_id_filter = user["user_id"]
    
    txns = db_manager.get_transactions_filtered(user_id=user_id_filter, category=category, txn_type=txn_type, start_date=start_date, end_date=end_date)
    return jsonify(txns)

@app.route("/api/transactions", methods=["POST"])
@role_required("manager")
def api_create_transaction():
    """Explicitly create a record (Admin functionality)"""
    data = request.json
    account_id = data.get("account_id")
    txn_type = data.get("txn_type")
    amount = data.get("amount", 0)
    category = data.get("category", "General")
    description = data.get("description", "Manual record creation")
    
    if not account_id or not txn_type or amount <= 0:
        return jsonify({"error": "Invalid input"}), 400
        
    db_manager.add_transaction(account_id, txn_type, amount, description, category=category)
    return jsonify({"success": True, "message": "Record created"})

@app.route("/api/transactions/<int:txn_id>", methods=["PUT"])
@role_required("manager")
def api_update_transaction(txn_id):
    data = request.json
    amount = data.get("amount")
    category = data.get("category")
    description = data.get("description")
    txn_type = data.get("txn_type")
    
    if None in (amount, category, description, txn_type):
        return jsonify({"error": "Missing fields"}), 400
        
    db_manager.update_transaction(txn_id, amount, category, description, txn_type)
    return jsonify({"success": True, "message": "Record updated"})

@app.route("/api/transactions/<int:txn_id>", methods=["DELETE"])
@role_required("manager")
def api_delete_transaction(txn_id):
    db_manager.delete_transaction(txn_id)
    return jsonify({"success": True, "message": "Record deleted"})

@app.route("/api/dashboard/summary", methods=["GET"])
@login_required
def api_dashboard_summary():
    user = session["user"]
    if user["role"] == "customer":
        # Specific user stats
        stats = db_manager.get_dashboard_summary(user_id=user["user_id"])
    else:
        # Analyst / Admin global stats
        stats = db_manager.get_dashboard_summary()
    return jsonify(stats)


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


@app.route("/api/users/create_with_account", methods=["POST"])
@role_required("manager")
def api_create_user_with_account():
    data = request.json
    manager_user = session["user"]

    username = data.get("username")
    password = data.get("password")
    full_name = data.get("full_name")
    role = data.get("role", "customer")
    email = data.get("email", "")
    phone = data.get("phone", "")
    account_type = data.get("account_type", "savings")
    balance = float(data.get("balance", 0))

    if db_manager.get_user_by_username(username):
        return jsonify({"error": "Username already exists"}), 400

    try:
        user_id, acc_id = db_manager.create_user_with_account(
            username=username,
            password_hash=hash_password(password),
            role=role,
            full_name=full_name,
            email=email,
            phone=phone,
            account_type=account_type,
            balance=balance
        )
        
        db_manager.add_system_log("USER_CREATED", manager_user["user_id"], f"Created {role}: {username} (with account)")
        if acc_id:
            db_manager.add_system_log("ACCOUNT_CREATED", manager_user["user_id"], f"Created account #{acc_id} for {username}")
            
        return jsonify({
            "success": True, 
            "user_id": user_id, 
            "account_id": acc_id,
            "message": f"User and Account created successfully" if acc_id else "User created successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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


@app.route("/api/users/<int:user_id>/unlock", methods=["POST"])
@role_required("manager")
def api_unlock_user(user_id):
    user = session["user"]
    if user_id == user["user_id"]:
        return jsonify({"error": "Cannot unlock your own account here"}), 400

    users = db_manager.get_all_users()
    target = None
    for u in users:
        if u["user_id"] == user_id:
            target = u
            break
            
    if not target:
        return jsonify({"error": "User not found"}), 404
        
    if not target["is_locked"]:
        return jsonify({"message": "User is already unlocked"}), 200

    db_manager.unlock_user(user_id)
    db_manager.add_system_log("USER_UNLOCKED", user["user_id"], f"Unlocked {target['username']} (web)")
    return jsonify({"success": True, "message": f"Successfully unlocked {target['username']}"})


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
# PROFILE & PASSWORD API
# ─────────────────────────────────────────────

@app.route("/api/profile")
@login_required
def api_get_profile():
    user = session["user"]
    u = db_manager.get_user_by_id(user["user_id"])
    if not u:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "user_id": u["user_id"], "username": u["username"], "full_name": u["full_name"],
        "role": u["role"], "email": u.get("email", ""), "phone": u.get("phone", ""),
        "address": u.get("address", ""), "created_at": u["created_at"],
        "qr_code_b64": u.get("qr_code_b64", ""), "avatar_b64": u.get("avatar_b64", "")
    })


@app.route("/api/profile", methods=["PUT"])
@login_required
def api_update_profile():
    data = request.json
    user = session["user"]
    db_manager.update_user_profile(
        user["user_id"],
        data.get("email", ""), data.get("phone", ""), data.get("address", "")
    )
    db_manager.add_system_log("PROFILE_UPDATED", user["user_id"], f"Profile updated by {user['username']}")
    return jsonify({"success": True})


@app.route("/api/profile/qr", methods=["POST"])
@login_required
def api_upload_qr():
    data = request.json
    qr_b64 = data.get("qr_code_b64", "")
    user = session["user"]
    
    # We store the raw base64 string provided by the frontend
    db_manager.update_user_qr(user["user_id"], qr_b64)
    db_manager.add_system_log("QR_UPDATED", user["user_id"], f"QR Code updated by {user['username']}")
    return jsonify({"success": True, "message": "QR Code updated successfully"})


@app.route("/api/account/<int:account_id>/qr", methods=["GET"])
@login_required
def api_get_account_qr(account_id):
    # This fetches the QR code of the user who owns the specified account.
    # Used for verifying payee identity before a transfer.
    qr_b64 = db_manager.get_user_qr_by_account_id(account_id)
    if not qr_b64:
        return jsonify({"error": "No QR code associated with this account."}), 404
        
    return jsonify({"success": True, "qr_code_b64": qr_b64})


@app.route("/api/change-password", methods=["POST"])
@login_required
def api_change_password():
    data = request.json
    user = session["user"]
    u = db_manager.get_user_by_id(user["user_id"])
    if not u:
        return jsonify({"error": "User not found"}), 404

    if not verify_password(data.get("old_password", ""), u["password_hash"]):
        return jsonify({"error": "Current password is incorrect"}), 400

    new_pass = data.get("new_password", "")
    if len(new_pass) < 4:
        return jsonify({"error": "New password must be at least 4 characters"}), 400

    db_manager.update_user_password(user["user_id"], hash_password(new_pass))
    db_manager.add_system_log("PASSWORD_CHANGED", user["user_id"], f"Password changed by {user['username']}")
    return jsonify({"success": True})


@app.route("/api/users/<int:user_id>/details")
@role_required("manager", "accountant")
def api_user_details(user_id):
    """Get full details for a customer: profile + accounts + transactions."""
    user = db_manager.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    accounts = db_manager.get_accounts_by_user(user_id)
    all_txns = []
    for acc in accounts:
        txns = db_manager.get_transactions_by_account(acc["account_id"], limit=50)
        all_txns.extend(txns)
    # Sort by timestamp descending
    all_txns.sort(key=lambda t: t.get("timestamp", ""), reverse=True)

    return jsonify({
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "address": user.get("address", ""),
            "is_active": user["is_active"],
            "is_locked": user.get("is_locked", False),
            "created_at": user.get("created_at", ""),
            "avatar_b64": user.get("avatar_b64", ""),
        },
        "accounts": accounts,
        "transactions": all_txns,
    })


# ─────────────────────────────────────────────
# BRANCH MANAGEMENT API
# ─────────────────────────────────────────────

@app.route("/api/branches")
@login_required
def api_get_branches():
    return jsonify(db_manager.get_branch_info())


@app.route("/api/branches", methods=["POST"])
@role_required("manager")
def api_create_branch():
    data = request.json
    user = session["user"]
    bid = db_manager.create_branch(data["branch_name"], data["location"], data.get("manager_id"))
    db_manager.add_system_log("BRANCH_CREATED", user["user_id"], f"Branch '{data['branch_name']}' created")
    return jsonify({"success": True, "branch_id": bid})


@app.route("/api/branches/<int:branch_id>", methods=["PUT"])
@role_required("manager")
def api_update_branch(branch_id):
    data = request.json
    user = session["user"]
    db_manager.update_branch(branch_id, data["branch_name"], data["location"], data.get("manager_id"))
    db_manager.add_system_log("BRANCH_UPDATED", user["user_id"], f"Branch #{branch_id} updated")
    return jsonify({"success": True})


@app.route("/api/branches/<int:branch_id>", methods=["DELETE"])
@role_required("manager")
def api_delete_branch(branch_id):
    user = session["user"]
    db_manager.delete_branch(branch_id)
    db_manager.add_system_log("BRANCH_DELETED", user["user_id"], f"Branch #{branch_id} deleted")
    return jsonify({"success": True})


# ─────────────────────────────────────────────
# MINI STATEMENT & RECEIPT API
# ─────────────────────────────────────────────

from logo_b64 import LOGO_B64

@app.route("/api/accounts/<int:account_id>/statement")
@login_required
def api_mini_statement(account_id):
    from datetime import datetime
    account = db_manager.get_account_by_id(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    user = session["user"]
    if user["role"] == "customer" and account["user_id"] != user["user_id"]:
        return jsonify({"error": "Access denied"}), 403

    start_date = request.args.get("start", "")
    end_date = request.args.get("end", "")

    txns = db_manager.get_transactions_by_account(account_id, limit=200)

    # Filter by date range if provided
    if start_date:
        txns = [t for t in txns if t["timestamp"][:10] >= start_date]
    if end_date:
        txns = [t for t in txns if t["timestamp"][:10] <= end_date]

    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    if start_date and end_date:
        period_label = f"Period: {start_date} to {end_date}"
    elif start_date:
        period_label = f"From: {start_date}"
    elif end_date:
        period_label = f"Until: {end_date}"
    else:
        period_label = "Recent Transactions"

    rows = ""
    for t in txns:
        color = "#16a34a" if t["txn_type"] == "deposit" else "#dc2626"
        sign = "+" if t["txn_type"] == "deposit" else "-"
        rows += f"""<tr>
            <td>{t['timestamp'][:10]}</td><td>{t['txn_type'].upper()}</td>
            <td>{t.get('description','')}</td>
            <td style="color:{color};font-weight:600">{sign}₹{t['amount']:,.2f}</td>
            <td>{t['status'].upper()}</td>
        </tr>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>ZenRupee — Statement</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
      body{{font-family:'Inter',sans-serif;padding:40px;color:#1a1a2e;max-width:800px;margin:0 auto}}
      .header{{text-align:center;border-bottom:3px solid #0c2340;padding-bottom:20px;margin-bottom:20px}}
      .header img{{width:52px;height:52px;margin-bottom:8px}}
      .header h1{{color:#0c2340;margin:0;font-size:1.5rem;letter-spacing:-0.01em}}
      .header .subtitle{{color:#64748b;margin:4px 0;font-size:0.85rem}}
      .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px;font-size:0.9rem}}
      .info-grid div{{padding:10px;background:#f1f5f9;border-radius:6px}}
      .info-grid strong{{color:#0c2340}}
      table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
      th{{background:#0c2340;color:white;padding:10px;text-align:left}}
      td{{padding:8px 10px;border-bottom:1px solid #e2e8f0}}
      tr:nth-child(even){{background:#f8fafc}}
      .footer{{text-align:center;margin-top:30px;font-size:0.75rem;color:#94a3b8;border-top:2px solid #e2e8f0;padding-top:15px}}
      .balance{{font-size:1.3rem;font-weight:700;color:#0c2340;text-align:right;margin:16px 0}}
      .stamp-container{{text-align:center;margin-top:24px}}
      .bank-stamp{{display:inline-block;border:3px solid #0c2340;border-radius:8px;padding:10px 24px;
                   transform:rotate(-4deg);opacity:0.7;text-align:center}}
      .bank-stamp .stamp-title{{color:#0c2340;font-weight:700;font-size:0.9rem;letter-spacing:0.05em}}
      .bank-stamp .stamp-sub{{color:#64748b;font-size:0.7rem;margin-top:2px}}
      .bank-stamp img{{width:30px;height:30px;margin-bottom:4px}}
      @media print{{body{{padding:20px}} .bank-stamp{{opacity:0.5}}}}
    </style></head><body>
    <div class="header">
      <img src="{LOGO_B64}" alt="ZenRupee">
      <h1>ZenRupee</h1>
      <p class="subtitle">Account Statement</p>
      <p class="subtitle">{period_label}</p>
      <p class="subtitle">Generated on {now}</p>
    </div>
    <div class="info-grid">
      <div><strong>Account No:</strong> {str(account_id).zfill(6)}</div>
      <div><strong>Account Type:</strong> {account['account_type'].upper()}</div>
      <div><strong>Account Holder:</strong> {account['customer_name']}</div>
      <div><strong>Status:</strong> {'Active' if account['is_active'] else 'Closed'}</div>
    </div>
    <div class="balance">Current Balance: ₹{account['balance']:,.2f}</div>
    <table><thead><tr><th>Date</th><th>Type</th><th>Description</th><th>Amount</th><th>Status</th></tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="5" style="text-align:center;padding:20px">No transactions found</td></tr>'}</tbody></table>
    <div class="stamp-container"><div class="bank-stamp">
      <img src="{LOGO_B64}" alt=""><div class="stamp-title">ZENRUPEE</div>
      <div class="stamp-sub">Authorised Statement</div>
    </div></div>
    <div class="footer"><p>This is a computer-generated statement and does not require a signature.</p>
    <p>ZenRupee &middot; Secure &middot; Reliable &middot; Trusted</p></div></body></html>"""

    return html, 200, {"Content-Type": "text/html"}


@app.route("/api/transactions/<int:txn_id>/receipt")
@login_required
def api_transaction_receipt(txn_id):
    from datetime import datetime
    txn = db_manager.get_transaction_by_id(txn_id)
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404

    account = db_manager.get_account_by_id(txn["account_id"])
    user = session["user"]
    if user["role"] == "customer" and account and account["user_id"] != user["user_id"]:
        return jsonify({"error": "Access denied"}), 403

    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    color = "#16a34a" if txn["txn_type"] == "deposit" else "#dc2626"
    sign = "+" if txn["txn_type"] == "deposit" else "-"

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>ZenRupee — Receipt</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
      body{{font-family:'Inter',sans-serif;padding:40px;color:#1a1a2e;max-width:500px;margin:0 auto}}
      .receipt{{border:2px solid #0c2340;border-radius:12px;padding:30px;position:relative}}
      .receipt::before{{content:'';position:absolute;top:0;left:0;right:0;height:6px;background:#0c2340;border-radius:10px 10px 0 0}}
      .header{{text-align:center;margin-bottom:24px}}
      .header img{{width:48px;height:48px;margin-bottom:6px}}
      .header h2{{color:#0c2340;margin:0;font-size:1.2rem}} .header p{{color:#94a3b8;font-size:0.8rem;margin:4px 0}}
      .amount{{text-align:center;font-size:2rem;font-weight:700;color:{color};margin:20px 0}}
      .details{{font-size:0.88rem}}
      .details .row{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #f1f5f9}}
      .details .row .label{{color:#64748b}} .details .row .value{{font-weight:600;color:#1a1a2e}}
      .footer{{text-align:center;margin-top:24px;font-size:0.72rem;color:#94a3b8}}
      .stamp-container{{text-align:center;margin-top:20px}}
      .bank-stamp{{display:inline-block;border:3px solid #16a34a;border-radius:8px;padding:8px 20px;
                   transform:rotate(-5deg);text-align:center}}
      .bank-stamp img{{width:24px;height:24px;margin-bottom:2px}}
      .bank-stamp .stamp-status{{color:#16a34a;font-weight:700;font-size:0.9rem;letter-spacing:0.05em}}
      .bank-stamp .stamp-bank{{color:#64748b;font-size:0.65rem;margin-top:2px}}
      @media print{{body{{padding:10px}} .receipt{{border:1px solid #ccc}}}}
    </style></head><body>
    <div class="receipt">
      <div class="header">
        <img src="{LOGO_B64}" alt="ZenRupee">
        <h2>ZenRupee</h2>
        <p>Transaction Receipt</p><p>{now}</p>
      </div>
      <div class="amount">{sign}₹{txn['amount']:,.2f}</div>
      <div class="details">
        <div class="row"><span class="label">Transaction ID</span><span class="value">TXN{str(txn['txn_id']).zfill(8)}</span></div>
        <div class="row"><span class="label">Type</span><span class="value">{txn['txn_type'].upper()}</span></div>
        <div class="row"><span class="label">Account No.</span><span class="value">{str(txn['account_id']).zfill(6)}</span></div>
        <div class="row"><span class="label">Date & Time</span><span class="value">{txn['timestamp']}</span></div>
        <div class="row"><span class="label">Description</span><span class="value">{txn.get('description','—')}</span></div>
        <div class="row"><span class="label">Status</span><span class="value">{txn['status'].upper()}</span></div>
        {'<div class="row"><span class="label">Target Account</span><span class="value">#' + str(txn['target_account_id']).zfill(6) + '</span></div>' if txn.get('target_account_id') else ''}
      </div>
      <div class="stamp-container"><div class="bank-stamp">
        <img src="{LOGO_B64}" alt="">
        <div class="stamp-status">{txn['status'].upper()}</div>
        <div class="stamp-bank">ZENRUPEE</div>
      </div></div>
      <div class="footer"><p>This is a computer-generated receipt.</p><p>ZenRupee</p></div>
    </div></body></html>"""

    return html, 200, {"Content-Type": "text/html"}
    return html, 200, {"Content-Type": "text/html"}

# ─────────────────────────────────────────────
# TICKETING API
# ─────────────────────────────────────────────

@app.route("/api/tickets", methods=["GET", "POST"])
@login_required
def api_tickets():
    user = session["user"]
    if request.method == "POST":
        data = request.json
        subject = data.get("subject", "").strip()
        if not subject:
            return jsonify({"error": "Subject is required"}), 400
        t_id = db_manager.create_ticket(user["user_id"], subject)
        db_manager.add_system_log("TICKET_CREATED", user["user_id"], f"Ticket #{t_id} created: {subject}")
        return jsonify({"success": True, "ticket_id": t_id})
    else:
        if user["role"] in ("manager", "accountant"):
            tickets = db_manager.get_all_tickets()
        else:
            tickets = db_manager.get_tickets_by_user(user["user_id"])
        
        # Hydrate user info for managers
        if user["role"] in ("manager", "accountant"):
            for t in tickets:
                u = db_manager.get_user_by_id(t["user_id"])
                t["customer_name"] = u["full_name"] if u else "Unknown"
        return jsonify(tickets)

@app.route("/api/tickets/<int:ticket_id>/messages", methods=["GET", "POST"])
@login_required
def api_ticket_messages(ticket_id):
    user = session["user"]
    
    # Just basic verification - manager/accountant can see all, customer can see own
    if user["role"] == "customer":
        tickets = db_manager.get_tickets_by_user(user["user_id"])
        if not any(t["ticket_id"] == ticket_id for t in tickets):
            return jsonify({"error": "Access denied"}), 403

    if request.method == "POST":
        data = request.json
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"error": "Message is required"}), 400
        m_id = db_manager.add_ticket_message(ticket_id, user["user_id"], message)
        return jsonify({"success": True, "message_id": m_id})
    else:
        msgs = db_manager.get_ticket_messages(ticket_id)
        # Hydrate names
        for m in msgs:
            u = db_manager.get_user_by_id(m["sender_user_id"])
            m["sender_name"] = u["full_name"] if u else "Unknown"
            m["sender_role"] = u["role"] if u else "customer"
        return jsonify(msgs)

@app.route("/api/tickets/<int:ticket_id>/close", methods=["POST"])
@role_required("manager", "accountant")
def api_ticket_close(ticket_id):
    db_manager.update_ticket_status(ticket_id, "closed")
    return jsonify({"success": True})


# ─────────────────────────────────────────────
# NOTIFICATIONS API
# ─────────────────────────────────────────────

@app.route("/api/notifications")
@login_required
def api_notifications():
    user = session["user"]
    return jsonify(db_manager.get_notifications(user["user_id"]))


@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def api_mark_read(notif_id):
    db_manager.mark_notification_read(notif_id)
    return jsonify({"success": True})


@app.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_mark_all_read():
    user = session["user"]
    db_manager.mark_all_notifications_read(user["user_id"])
    return jsonify({"success": True})


@app.route("/api/notifications/unread-count")
@login_required
def api_unread_count():
    user = session["user"]
    return jsonify({"count": db_manager.get_unread_notification_count(user["user_id"])})


# ─────────────────────────────────────────────
# BENEFICIARIES API
# ─────────────────────────────────────────────

@app.route("/api/beneficiaries")
@login_required
def api_get_beneficiaries():
    user = session["user"]
    return jsonify(db_manager.get_beneficiaries(user["user_id"]))


@app.route("/api/beneficiaries", methods=["POST"])
@login_required
def api_add_beneficiary():
    data = request.json
    user = session["user"]
    db_manager.add_beneficiary(user["user_id"], data["name"], data["account_id"], data.get("nickname", ""))
    return jsonify({"success": True})


@app.route("/api/beneficiaries/<int:ben_id>", methods=["DELETE"])
@login_required
def api_delete_beneficiary(ben_id):
    db_manager.delete_beneficiary(ben_id)
    return jsonify({"success": True})


# ─────────────────────────────────────────────
# LOANS API
# ─────────────────────────────────────────────

@app.route("/api/loans/apply", methods=["POST"])
@login_required
def api_apply_loan():
    data = request.json
    user = session["user"]
    amount = float(data["amount"])
    tenure = int(data["tenure"])
    account_id = int(data["account_id"])

    # Basic EMI calculation (10.5% annual interest)
    interest_rate = 10.5 / 100 / 12
    emi = (amount * interest_rate * (1 + interest_rate)**tenure) / ((1 + interest_rate)**tenure - 1)

    db_manager.apply_loan(user["user_id"], account_id, amount, tenure, emi)
    db_manager.add_notification(user["user_id"], f"Loan application for ₹{amount:,.2f} submitted.", "info")
    return jsonify({"success": True, "emi": emi})


@app.route("/api/loans")
@login_required
def api_get_loans():
    user = session["user"]
    if user["role"] in ["manager", "accountant"]:
        return jsonify(db_manager.get_all_loans())
    return jsonify(db_manager.get_loans_by_user(user["user_id"]))


@app.route("/api/loans/<int:loan_id>/accountant-review", methods=["POST"])
@role_required("accountant")
def api_accountant_review_loan(loan_id):
    acc = session["user"]
    data = request.json
    status = data.get("status") # 'approved' or 'rejected'
    
    loan = db_manager.get_loan_by_id(loan_id)
    if not loan:
        return jsonify({"error": "Loan not found"}), 404

    if status == "approved":
        db_manager.update_loan_status(loan_id, "pending", acc["username"], accountant_status="approved")
        db_manager.add_notification(loan["user_id"], f"Your loan application #{loan_id} has been verified by the accountant. Awaiting manager approval.", "info")
    else:
        db_manager.update_loan_status(loan_id, "rejected", acc["username"], accountant_status="rejected")
        db_manager.add_notification(loan["user_id"], f"Your loan application #{loan_id} was rejected by the accountant.", "warning")
        
    return jsonify({"success": True})


@app.route("/api/loans/<int:loan_id>/approve", methods=["POST"])
@role_required("manager")
def api_approve_loan(loan_id):
    mgr = session["user"]
    loan = db_manager.get_loan_by_id(loan_id)
    if not loan:
        return jsonify({"error": "Loan not found"}), 404

    if loan["accountant_status"] != "approved":
        return jsonify({"error": "Loan must be approved by an accountant first"}), 400

    db_manager.update_loan_status(loan_id, "active", mgr["username"], manager_status="approved")

    # Disburse loan amount to account
    acc = db_manager.get_account_by_id(loan["account_id"])
    db_manager.update_balance(loan["account_id"], acc["balance"] + loan["loan_amount"])
    db_manager.add_transaction(loan["account_id"], "deposit", loan["loan_amount"], f"Loan Disbursement #{loan_id}", "completed")

    db_manager.add_notification(loan["user_id"], f"Loan of ₹{loan['loan_amount']:,.2f} has been fully approved and disbursed!", "success")
    return jsonify({"success": True})


@app.route("/api/loans/<int:loan_id>/reject", methods=["POST"])
@role_required("manager", "accountant")
def api_reject_loan(loan_id):
    user = session["user"]
    loan = db_manager.get_loan_by_id(loan_id)
    if not loan:
        return jsonify({"error": "Loan not found"}), 404

    role_field = "manager_status" if user["role"] == "manager" else "accountant_status"
    update_params = {role_field: "rejected"}
    db_manager.update_loan_status(loan_id, "rejected", user["username"], **update_params)
    db_manager.add_notification(loan["user_id"], f"Loan application #{loan_id} was rejected by {user['role']}.", "warning")
    return jsonify({"success": True})
    return jsonify({"success": True})


@app.route("/api/loans/<int:loan_id>/pay-emi", methods=["POST"])
@login_required
def api_pay_emi(loan_id):
    user = session["user"]
    loan = db_manager.get_loan_by_id(loan_id)
    if not loan or loan["user_id"] != user["user_id"]:
        return jsonify({"error": "Loan not found"}), 404

    acc = db_manager.get_account_by_id(loan["account_id"])
    if acc["balance"] < loan["emi_amount"]:
        return jsonify({"error": "Insufficient balance in linked account"}), 400

    # Process payment
    db_manager.update_balance(loan["account_id"], acc["balance"] - loan["emi_amount"])
    db_manager.add_transaction(loan["account_id"], "withdrawal", loan["emi_amount"], f"EMI Payment — Loan #{loan_id}", "completed")
    db_manager.make_emi_payment(loan_id, loan["emi_amount"])

    db_manager.add_notification(user["user_id"], f"EMI of ₹{loan['emi_amount']:,.2f} paid for Loan #{loan_id}.", "success")
    return jsonify({"success": True})


# ─────────────────────────────────────────────
# QR CODE API
# ─────────────────────────────────────────────

@app.route("/api/accounts/<int:account_id>/qr", methods=["GET", "POST"])
@login_required
def api_account_qr(account_id):
    account = db_manager.get_account_by_id(account_id)
    if not account:
        return jsonify({"success": False, "message": "Account not found"}), 404
    
    # Permission check: For GET, any logged in user can see (to pay). For POST, only owner/staff.
    user = session["user"]
    is_owner = account["user_id"] == user["user_id"]
    is_staff = user["role"] in ["accountant", "manager"]

    if request.method == "POST":
        if not (is_owner or is_staff):
            return jsonify({"success": False, "message": "Unauthorized"}), 403
        data = request.json
        qr_data = data.get("qr_code") # Expecting base64 string
        if not qr_data:
            return jsonify({"success": False, "message": "No QR data provided"}), 400
        db_manager.update_account_qr(account_id, qr_data)
        return jsonify({"success": True})
    
    # GET
    qr_data = db_manager.get_account_qr(account_id)
    return jsonify({"success": True, "qr_code": qr_data})


# ─────────────────────────────────────────────
# MAIN
# CREDIT CARDS API
# ─────────────────────────────────────────────

@app.route("/api/credit_cards", methods=["GET"])
@login_required
def api_credit_cards():
    user = session["user"]
    if user["role"] == "customer":
        accounts = db_manager.get_accounts_by_user(user["user_id"])
        cards = []
        for acc in accounts:
            cards.extend(db_manager.get_credit_cards_by_account(acc["account_id"]))
        return jsonify(cards)
    else:
        # Staff (accountant/manager) can see all cards
        return jsonify(db_manager.get_all_credit_cards())

@app.route("/api/credit_cards/apply", methods=["POST"])
@role_required("customer")
def api_credit_card_apply():
    user = session["user"]
    data = request.json
    account_id = data.get("account_id")
    limit_requested = data.get("limit_requested", 0)
    
    account = db_manager.get_account_by_id(account_id)
    if not account or account["user_id"] != user["user_id"]:
        return jsonify({"error": "Invalid account"}), 400
        
    db_manager.create_request(account_id, "credit_card", limit_requested, f"Requested Limit: ₹{limit_requested:,.2f}")
    db_manager.notify_staff(f"New credit card application for Limit ₹{limit_requested:,.2f} from Account #{account_id}.")
    return jsonify({"success": True, "message": "Credit card application submitted to management."})

@app.route("/api/credit_cards/pay", methods=["POST"])
@role_required("customer")
def api_credit_card_pay():
    user = session["user"]
    data = request.json
    src_account_id = data.get("account_id")
    card_id = data.get("card_id")
    amount = data.get("amount", 0)

    account = db_manager.get_account_by_id(src_account_id)
    if not account or account["user_id"] != user["user_id"] or account["balance"] < amount:
        return jsonify({"error": "Insufficient balance or invalid account"}), 400

    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400

    # Subtract from checking
    new_bal = account["balance"] - amount
    db_manager.update_balance(src_account_id, new_bal)
    db_manager.add_transaction(src_account_id, "withdrawal", amount, f"Credit Card Bill Payment (Card #{card_id})")

    # Fetch card and deduct balance
    c = db_manager.get_credit_card_by_id(card_id)
    if not c:
        return jsonify({"error": "Card not found"}), 404
        
    new_card_bal = max(0, c["current_balance"] - amount)
    db_manager.update_credit_card_balance(card_id, new_card_bal)
    
    return jsonify({"success": True, "new_card_balance": new_card_bal, "new_account_balance": new_bal})

# ─────────────────────────────────────────────
# AVATAR API
# ─────────────────────────────────────────────

@app.route("/api/profile/avatar", methods=["POST"])
@login_required
def api_profile_avatar():
    try:
        data = request.json
        b64 = data.get("avatar_b64")
        if not b64:
            return jsonify({"error": "Image data missing"}), 400
        
        user_id = session["user"]["user_id"]
        db_manager.update_user_avatar(user_id, b64)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    db_manager.init_all_databases()
    print("\n  ZenRupee — Web Server")
    print("  http://localhost:5005\n")
    app.run(debug=True, host="0.0.0.0", port=5005, use_reloader=False)



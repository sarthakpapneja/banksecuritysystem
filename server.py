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


# ─────────────────────────────────────────────
# UNLOCK USER API
# ─────────────────────────────────────────────

@app.route("/api/users/<int:user_id>/unlock", methods=["POST"])
@role_required("manager", "accountant")
def api_unlock_user(user_id):
    user = session["user"]
    db_manager.unlock_user(user_id)
    db_manager.add_system_log("ACCOUNT_UNLOCKED", user["user_id"], f"Unlocked user #{user_id}")
    return jsonify({"success": True})


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

    txns = db_manager.get_transactions_by_account(account_id, limit=20)
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

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

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Mini Statement</title>
    <style>
      body{{font-family:'Inter',sans-serif;padding:40px;color:#1a1a2e;max-width:800px;margin:0 auto}}
      .header{{text-align:center;border-bottom:3px solid #0c2340;padding-bottom:20px;margin-bottom:20px}}
      .header h1{{color:#0c2340;margin:0;font-size:1.5rem}} .header p{{color:#64748b;margin:4px 0;font-size:0.85rem}}
      .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px;font-size:0.9rem}}
      .info-grid div{{padding:10px;background:#f1f5f9;border-radius:6px}}
      .info-grid strong{{color:#0c2340}}
      table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
      th{{background:#0c2340;color:white;padding:10px;text-align:left}}
      td{{padding:8px 10px;border-bottom:1px solid #e2e8f0}}
      tr:nth-child(even){{background:#f8fafc}}
      .footer{{text-align:center;margin-top:30px;font-size:0.75rem;color:#94a3b8;border-top:2px solid #e2e8f0;padding-top:15px}}
      .balance{{font-size:1.3rem;font-weight:700;color:#0c2340;text-align:right;margin:16px 0}}
      @media print{{body{{padding:20px}}}}
    </style></head><body>
    <div class="header"><h1>🏦 Bank Security System</h1><p>Mini Statement / Passbook</p><p>Generated on {now}</p></div>
    <div class="info-grid">
      <div><strong>Account No:</strong> {str(account_id).zfill(6)}</div>
      <div><strong>Account Type:</strong> {account['account_type'].upper()}</div>
      <div><strong>Account Holder:</strong> {account['customer_name']}</div>
      <div><strong>Status:</strong> {'Active' if account['is_active'] else 'Closed'}</div>
    </div>
    <div class="balance">Current Balance: ₹{account['balance']:,.2f}</div>
    <table><thead><tr><th>Date</th><th>Type</th><th>Description</th><th>Amount</th><th>Status</th></tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="5" style="text-align:center;padding:20px">No transactions found</td></tr>'}</tbody></table>
    <div class="footer"><p>This is a computer-generated statement and does not require a signature.</p>
    <p>Bank Security System · Secure · Reliable · Role-Based Access</p></div></body></html>"""

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

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Transaction Receipt</title>
    <style>
      body{{font-family:'Inter',sans-serif;padding:40px;color:#1a1a2e;max-width:500px;margin:0 auto}}
      .receipt{{border:2px solid #0c2340;border-radius:12px;padding:30px;position:relative}}
      .receipt::before{{content:'';position:absolute;top:0;left:0;right:0;height:6px;background:#0c2340;border-radius:10px 10px 0 0}}
      .header{{text-align:center;margin-bottom:24px}}
      .header h2{{color:#0c2340;margin:0;font-size:1.2rem}} .header p{{color:#94a3b8;font-size:0.8rem;margin:4px 0}}
      .amount{{text-align:center;font-size:2rem;font-weight:700;color:{color};margin:20px 0}}
      .details{{font-size:0.88rem}}
      .details .row{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #f1f5f9}}
      .details .row .label{{color:#64748b}} .details .row .value{{font-weight:600;color:#1a1a2e}}
      .footer{{text-align:center;margin-top:24px;font-size:0.72rem;color:#94a3b8}}
      .stamp{{text-align:center;margin-top:16px;color:#16a34a;font-weight:700;font-size:0.9rem;
              border:2px solid #16a34a;display:inline-block;padding:4px 16px;border-radius:4px;transform:rotate(-5deg)}}
      @media print{{body{{padding:10px}} .receipt{{border:1px solid #ccc}}}}
    </style></head><body>
    <div class="receipt">
      <div class="header"><h2>🏦 Bank Security System</h2><p>Transaction Receipt</p><p>{now}</p></div>
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
      <div style="text-align:center;margin-top:20px"><span class="stamp">✓ {txn['status'].upper()}</span></div>
      <div class="footer"><p>This is a computer-generated receipt.</p><p>Bank Security System</p></div>
    </div></body></html>"""

    return html, 200, {"Content-Type": "text/html"}


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    db_manager.init_all_databases()
    print("\n🏦 Bank Security System — Web UI")
    print("   http://localhost:5001\n")
    app.run(debug=True, port=5001)


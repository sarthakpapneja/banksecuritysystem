"""
Bank Security System - Seed Data
Populates all 3 databases with demo users, accounts, and sample data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_manager
from auth import hash_password


def seed_all():
    """Seed all databases with demo data."""

    print("🏦 Initializing databases...")
    db_manager.init_all_databases()

    # ── Users (managers.db) ──────────────────────────
    print("👤 Creating users...")

    users = [
        ("john_doe",    "password123", "customer",   "John Doe"),
        ("jane_smith",  "password123", "customer",   "Jane Smith"),
        ("mike_wilson", "password123", "customer",   "Mike Wilson"),
        ("acc_smith",   "password123", "accountant", "Alice Smith"),
        ("acc_jones",   "password123", "accountant", "Bob Jones"),
        ("mgr_admin",   "admin123",    "manager",    "Sarah Admin"),
    ]

    user_ids = {}
    for username, password, role, full_name in users:
        existing = db_manager.get_user_by_username(username)
        if existing:
            user_ids[username] = existing["user_id"]
            print(f"   ⏩ User '{username}' already exists, skipping.")
        else:
            uid = db_manager.create_user(username, hash_password(password), role, full_name)
            user_ids[username] = uid
            print(f"   ✅ Created {role}: {username} (ID: {uid})")

    # ── Accounts (customers.db) ──────────────────────
    print("\n💳 Creating bank accounts...")

    existing_accounts = db_manager.get_all_accounts()
    if existing_accounts:
        print("   ⏩ Accounts already exist, skipping.")
    else:
        accounts_data = [
            ("John Doe",    "john@email.com",  "555-0101", 15000.00, "savings", user_ids["john_doe"]),
            ("John Doe",    "john@email.com",  "555-0101", 50000.00, "current", user_ids["john_doe"]),
            ("Jane Smith",  "jane@email.com",  "555-0102", 25000.00, "savings", user_ids["jane_smith"]),
            ("Mike Wilson", "mike@email.com",  "555-0103",  8000.00, "savings", user_ids["mike_wilson"]),
            ("Mike Wilson", "mike@email.com",  "555-0103", 120000.00, "fixed_deposit", user_ids["mike_wilson"]),
        ]

        for name, email, phone, balance, acc_type, uid in accounts_data:
            acc_id = db_manager.create_account(name, email, phone, balance, acc_type, uid)
            print(f"   ✅ Account #{acc_id}: {name} ({acc_type}) — ₹{balance:,.2f}")

    # ── Transactions (customers.db) ──────────────────
    print("\n📝 Adding sample transactions...")

    accounts = db_manager.get_all_accounts()
    existing_txns = db_manager.get_all_transactions()
    if existing_txns:
        print("   ⏩ Transactions already exist, skipping.")
    else:
        txns = [
            (accounts[0]["account_id"], "deposit",    5000.00, "Salary credit"),
            (accounts[0]["account_id"], "withdrawal", 2000.00, "ATM withdrawal"),
            (accounts[0]["account_id"], "transfer",   3000.00, "Rent payment"),
            (accounts[1]["account_id"], "deposit",   10000.00, "Business income"),
            (accounts[2]["account_id"], "deposit",    7500.00, "Freelance payment"),
            (accounts[2]["account_id"], "withdrawal", 1500.00, "Grocery shopping"),
            (accounts[3]["account_id"], "deposit",    3000.00, "Monthly savings"),
        ]

        for acc_id, txn_type, amount, desc in txns:
            tid = db_manager.add_transaction(acc_id, txn_type, amount, desc)
            print(f"   ✅ Txn #{tid}: {txn_type} ₹{amount:,.2f} — {desc}")

    # ── Pending Requests (accountants.db) ─────────────
    print("\n📋 Creating sample pending requests...")

    existing_reqs = db_manager.get_all_requests()
    if existing_reqs:
        print("   ⏩ Requests already exist, skipping.")
    else:
        requests = [
            (accounts[0]["account_id"], "large_withdrawal", 10000.00, "Emergency medical expense"),
            (accounts[2]["account_id"], "large_transfer",    8000.00, "Property down payment"),
            (accounts[3]["account_id"], "account_close",        0.00, "Customer requested closure"),
        ]

        for acc_id, req_type, amount, details in requests:
            rid = db_manager.create_request(acc_id, req_type, amount, details)
            print(f"   ✅ Request #{rid}: {req_type} — {details}")

    # ── Branch Info (managers.db) ─────────────────────
    print("\n🏛  Adding branch info...")

    branches = db_manager.get_branch_info()
    if branches:
        print("   ⏩ Branches already exist, skipping.")
    else:
        conn = db_manager.get_connection("managers")
        cursor = conn.cursor()
        branch_data = [
            ("Main Branch",   "123 Financial District, Mumbai",  user_ids["mgr_admin"]),
            ("North Branch",  "456 Business Park, Delhi",        None),
            ("South Branch",  "789 Tech Hub, Bangalore",         None),
        ]
        for name, location, mgr_id in branch_data:
            cursor.execute(
                "INSERT INTO branch_info (branch_name, location, manager_id) VALUES (?, ?, ?)",
                (name, location, mgr_id)
            )
            print(f"   ✅ Branch: {name} — {location}")
        conn.commit()
        conn.close()

    # ── Audit Logs (accountants.db) ───────────────────
    print("\n📊 Adding sample audit entries...")
    db_manager.add_audit_log("SYSTEM_INIT", "system", details="Database seeded with demo data")
    print("   ✅ Added system init audit entry")

    print("\n" + "═" * 50)
    print("✅ All databases seeded successfully!")
    print("═" * 50)
    print("\n📌 Demo Credentials:")
    print("   Customer:   john_doe / password123")
    print("   Customer:   jane_smith / password123")
    print("   Customer:   mike_wilson / password123")
    print("   Accountant: acc_smith / password123")
    print("   Accountant: acc_jones / password123")
    print("   Manager:    mgr_admin / admin123")
    print()


if __name__ == "__main__":
    seed_all()

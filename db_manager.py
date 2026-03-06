"""
Bank Security System - Database Manager
Handles all database operations across 3 separate SQLite databases.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional

# Database directory
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get_db_path(db_name: str) -> str:
    """Get the absolute path to a database file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"{db_name}.db")


def get_connection(db_name: str) -> sqlite3.Connection:
    """Get a database connection with row_factory set."""
    conn = sqlite3.connect(get_db_path(db_name))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─────────────────────────────────────────────
# Schema Initialization
# ─────────────────────────────────────────────

def init_customers_db():
    """Create tables in customers.db."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT    NOT NULL,
            email         TEXT    NOT NULL,
            phone         TEXT    NOT NULL,
            balance       REAL    DEFAULT 0.0,
            account_type  TEXT    DEFAULT 'savings',
            user_id       INTEGER NOT NULL,
            branch_id     INTEGER DEFAULT NULL,
            created_at    TEXT    DEFAULT (datetime('now','localtime')),
            is_active     INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS transactions (
            txn_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id        INTEGER NOT NULL,
            txn_type          TEXT    NOT NULL,
            amount            REAL    NOT NULL,
            timestamp         TEXT    DEFAULT (datetime('now','localtime')),
            description       TEXT    DEFAULT '',
            status            TEXT    DEFAULT 'completed',
            target_account_id INTEGER,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        );
    """)
    conn.commit()
    conn.close()


def init_accountants_db():
    """Create tables in accountants.db."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS pending_requests (
            request_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id   INTEGER NOT NULL,
            request_type TEXT    NOT NULL,
            amount       REAL    DEFAULT 0.0,
            status       TEXT    DEFAULT 'pending',
            created_at   TEXT    DEFAULT (datetime('now','localtime')),
            processed_by TEXT,
            details      TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            action       TEXT    NOT NULL,
            performed_by TEXT    NOT NULL,
            account_id   INTEGER,
            timestamp    TEXT    DEFAULT (datetime('now','localtime')),
            details      TEXT    DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()


def init_managers_db():
    """Create tables in managers.db."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL,
            role            TEXT    NOT NULL DEFAULT 'customer',
            full_name       TEXT    NOT NULL,
            email           TEXT    DEFAULT '',
            phone           TEXT    DEFAULT '',
            address         TEXT    DEFAULT '',
            created_at      TEXT    DEFAULT (datetime('now','localtime')),
            is_active       INTEGER DEFAULT 1,
            failed_attempts INTEGER DEFAULT 0,
            is_locked       INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS system_logs (
            log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            action     TEXT    NOT NULL,
            user_id    INTEGER NOT NULL,
            timestamp  TEXT    DEFAULT (datetime('now','localtime')),
            ip_address TEXT    DEFAULT '127.0.0.1',
            details    TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS branch_info (
            branch_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_name TEXT    NOT NULL,
            location    TEXT    NOT NULL,
            manager_id  INTEGER
        );
    """)
    conn.commit()
    conn.close()


def init_all_databases():
    """Initialize all three databases."""
    init_customers_db()
    init_accountants_db()
    init_managers_db()


# ─────────────────────────────────────────────
# USER Operations (managers.db)
# ─────────────────────────────────────────────

def create_user(username: str, password_hash: str, role: str, full_name: str) -> int:
    """Create a new user and return the user_id."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
        (username, password_hash, role, full_name)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_user_by_username(username: str) -> Optional[dict]:
    """Fetch a user by username."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Fetch a user by user_id."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users() -> list:
    """Fetch all users."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, role, full_name, created_at, is_active, is_locked FROM users ORDER BY user_id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_user_active(user_id: int, active: bool):
    """Enable or disable a user account."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (1 if active else 0, user_id))
    conn.commit()
    conn.close()


def update_user_password(user_id: int, new_hash: str):
    """Update a user's password hash."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()


def update_user_profile(user_id: int, email: str, phone: str, address: str):
    """Update a user's profile fields."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email = ?, phone = ?, address = ? WHERE user_id = ?",
                   (email, phone, address, user_id))
    conn.commit()
    conn.close()


def increment_failed_attempts(user_id: int) -> int:
    """Increment failed login attempts. Returns new count."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET failed_attempts = failed_attempts + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    cursor.execute("SELECT failed_attempts FROM users WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def reset_failed_attempts(user_id: int):
    """Reset failed login attempts to 0."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET failed_attempts = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def lock_user(user_id: int):
    """Lock a user account."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_locked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def unlock_user(user_id: int):
    """Unlock a user account and reset failed attempts."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_locked = 0, failed_attempts = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def delete_user(user_id: int):
    """Delete a user and close all their associated accounts."""
    cust_conn = get_connection("customers")
    cust_cursor = cust_conn.cursor()
    cust_cursor.execute("UPDATE accounts SET is_active = 0 WHERE user_id = ?", (user_id,))
    cust_conn.commit()
    cust_conn.close()

    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# ACCOUNT Operations (customers.db)
# ─────────────────────────────────────────────

def create_account(customer_name: str, email: str, phone: str, balance: float,
                   account_type: str, user_id: int) -> int:
    """Create a new bank account."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO accounts (customer_name, email, phone, balance, account_type, user_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (customer_name, email, phone, balance, account_type, user_id)
    )
    conn.commit()
    acc_id = cursor.lastrowid
    conn.close()
    return acc_id


def get_accounts_by_user(user_id: int) -> list:
    """Get all accounts for a given user."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE user_id = ? AND is_active = 1", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account_by_id(account_id: int) -> Optional[dict]:
    """Get a single account by ID."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_accounts() -> list:
    """Get all accounts."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts ORDER BY account_id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_balance(account_id: int, new_balance: float):
    """Update the balance for an account."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET balance = ? WHERE account_id = ?", (new_balance, account_id))
    conn.commit()
    conn.close()


def close_account(account_id: int):
    """Close an account (set is_active = 0)."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET is_active = 0 WHERE account_id = ?", (account_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# TRANSACTION Operations (customers.db)
# ─────────────────────────────────────────────

def add_transaction(account_id: int, txn_type: str, amount: float,
                    description: str = "", status: str = "completed",
                    target_account_id: int = None) -> int:
    """Record a transaction."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO transactions (account_id, txn_type, amount, description, status, target_account_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (account_id, txn_type, amount, description, status, target_account_id)
    )
    conn.commit()
    txn_id = cursor.lastrowid
    conn.close()
    return txn_id


def get_transactions_by_account(account_id: int, limit: int = 20) -> list:
    """Get recent transactions for an account."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE account_id = ? ORDER BY timestamp DESC LIMIT ?",
        (account_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_transactions(limit: int = 50) -> list:
    """Get all recent transactions across all accounts."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# PENDING REQUESTS (accountants.db)
# ─────────────────────────────────────────────

def create_request(account_id: int, request_type: str, amount: float, details: str = "") -> int:
    """Create a pending request for accountant review."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO pending_requests (account_id, request_type, amount, details)
           VALUES (?, ?, ?, ?)""",
        (account_id, request_type, amount, details)
    )
    conn.commit()
    req_id = cursor.lastrowid
    conn.close()
    return req_id


def get_pending_requests() -> list:
    """Get all pending requests."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pending_requests WHERE status = 'pending' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_requests() -> list:
    """Get all requests (any status)."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pending_requests ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_request_status(request_id: int, status: str, processed_by: str):
    """Update a pending request's status."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE pending_requests SET status = ?, processed_by = ? WHERE request_id = ?",
        (status, processed_by, request_id)
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# AUDIT LOG (accountants.db)
# ─────────────────────────────────────────────

def add_audit_log(action: str, performed_by: str, account_id: int = None, details: str = ""):
    """Record an action in the audit log."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO audit_log (action, performed_by, account_id, details) VALUES (?, ?, ?, ?)",
        (action, performed_by, account_id, details)
    )
    conn.commit()
    conn.close()


def get_audit_logs(limit: int = 30) -> list:
    """Get recent audit log entries."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# SYSTEM LOGS (managers.db)
# ─────────────────────────────────────────────

def add_system_log(action: str, user_id: int, details: str = ""):
    """Record a system-level event."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_logs (action, user_id, details) VALUES (?, ?, ?)",
        (action, user_id, details)
    )
    conn.commit()
    conn.close()


def get_system_logs(limit: int = 30) -> list:
    """Get recent system log entries."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# BRANCH INFO (managers.db)
# ─────────────────────────────────────────────

def get_branch_info() -> list:
    """Get all branches."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM branch_info ORDER BY branch_id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_branch(branch_name: str, location: str, manager_id: int = None) -> int:
    """Create a new branch."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO branch_info (branch_name, location, manager_id) VALUES (?, ?, ?)",
        (branch_name, location, manager_id)
    )
    conn.commit()
    bid = cursor.lastrowid
    conn.close()
    return bid


def update_branch(branch_id: int, branch_name: str, location: str, manager_id: int = None):
    """Update an existing branch."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE branch_info SET branch_name = ?, location = ?, manager_id = ? WHERE branch_id = ?",
        (branch_name, location, manager_id, branch_id)
    )
    conn.commit()
    conn.close()


def delete_branch(branch_id: int):
    """Delete a branch."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM branch_info WHERE branch_id = ?", (branch_id,))
    conn.commit()
    conn.close()


def get_transaction_by_id(txn_id: int) -> Optional[dict]:
    """Get a single transaction by ID."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# REPORTING / ANALYTICS (cross-database)
# ─────────────────────────────────────────────

def get_total_deposits() -> float:
    """Sum of all deposits."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE txn_type = 'deposit'")
    total = cursor.fetchone()[0]
    conn.close()
    return total


def get_total_withdrawals() -> float:
    """Sum of all withdrawals."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE txn_type = 'withdrawal'")
    total = cursor.fetchone()[0]
    conn.close()
    return total


def get_total_balance() -> float:
    """Sum of all account balances."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE is_active = 1")
    total = cursor.fetchone()[0]
    conn.close()
    return total


def get_account_count() -> int:
    """Count of active accounts."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_active = 1")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_user_count() -> int:
    """Count of active users."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    count = cursor.fetchone()[0]
    conn.close()
    return count

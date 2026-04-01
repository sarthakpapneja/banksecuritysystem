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
            is_active     INTEGER DEFAULT 1,
            qr_code       TEXT    DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS transactions (
            txn_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id        INTEGER NOT NULL,
            txn_type          TEXT    NOT NULL,
            amount            REAL    NOT NULL,
            category          TEXT    DEFAULT 'General',
            timestamp         TEXT    DEFAULT (datetime('now','localtime')),
            description       TEXT    DEFAULT '',
            status            TEXT    DEFAULT 'completed',
            target_account_id INTEGER,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        );

        -- Expanded Loans Table (Remote)
        CREATE TABLE IF NOT EXISTS loans (
            loan_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            account_id        INTEGER NOT NULL,
            loan_amount       REAL    NOT NULL,
            interest_rate     REAL    DEFAULT 10.5,
            tenure_months     INTEGER NOT NULL,
            emi_amount        REAL    NOT NULL,
            total_paid        REAL    DEFAULT 0.0,
            status            TEXT    DEFAULT 'pending',
            accountant_status TEXT    DEFAULT 'pending',
            manager_status    TEXT    DEFAULT 'pending',
            applied_at        TEXT    DEFAULT (datetime('now','localtime')),
            approved_by       TEXT    DEFAULT '',
            approved_at       TEXT    DEFAULT '',
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        );

        -- Beneficiaries Table (Remote Structure)
        CREATE TABLE IF NOT EXISTS beneficiaries (
            ben_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            name       TEXT    NOT NULL,
            account_id INTEGER NOT NULL,
            nickname   TEXT    DEFAULT '',
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS security_alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            message    TEXT    NOT NULL,
            type       TEXT    NOT NULL,
            is_read    INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        );

        -- Active Loans (My specific implementation)
        CREATE TABLE IF NOT EXISTS active_loans (
            loan_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id               INTEGER NOT NULL,
            principal                REAL    NOT NULL,
            interest_rate            REAL    NOT NULL,
            term_months              INTEGER NOT NULL,
            total_cost_with_interest REAL    NOT NULL,
            remaining_balance        REAL    NOT NULL,
            next_emi_amount          REAL    NOT NULL,
            created_at               TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        );

        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            subject    TEXT    NOT NULL,
            status     TEXT    DEFAULT 'open',
            created_at TEXT    DEFAULT (datetime('now','localtime')),
            updated_at TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS ticket_messages (
            message_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id      INTEGER NOT NULL,
            sender_user_id INTEGER NOT NULL,
            message        TEXT    NOT NULL,
            created_at     TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(ticket_id) REFERENCES support_tickets(ticket_id)
        );

        CREATE TABLE IF NOT EXISTS credit_cards (
            card_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id      INTEGER NOT NULL,
            card_number     TEXT    NOT NULL UNIQUE,
            credit_limit    REAL    NOT NULL,
            current_balance REAL    DEFAULT 0,
            apr             REAL    NOT NULL,
            due_date        TEXT,
            status          TEXT    DEFAULT 'active',
            FOREIGN KEY(account_id) REFERENCES accounts(account_id)
        );
    """)
    
    # Migration: Add qr_code to accounts if missing
    cursor = conn.execute("PRAGMA table_info(accounts)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "qr_code" not in columns:
        conn.execute("ALTER TABLE accounts ADD COLUMN qr_code TEXT DEFAULT NULL")

    # Migration: Add category to transactions if missing
    cursor = conn.execute("PRAGMA table_info(transactions)")
    txn_columns = [row["name"] for row in cursor.fetchall()]
    if "category" not in txn_columns:
        conn.execute("ALTER TABLE transactions ADD COLUMN category TEXT DEFAULT 'General'")

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
            qr_code_b64     TEXT    DEFAULT '',
            avatar_b64      TEXT    DEFAULT '',
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

        CREATE TABLE IF NOT EXISTS notifications (
            notif_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            message    TEXT    NOT NULL,
            type       TEXT    DEFAULT 'info',
            is_read    INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        );
    """)
    
    # Safely alter users table to add missing columns if they don't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_b64 TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass # Column might already exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN qr_code_b64 TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass # Column might already exist


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
    return user_id if user_id is not None else 0


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
    """Update user's profile information."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET email = ?, phone = ?, address = ? WHERE user_id = ?",
        (email, phone, address, user_id)
    )
    conn.commit()
    conn.close()


def update_user_qr(user_id: int, qr_b64: str):
    """Update a user's base64 QR code image."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET qr_code_b64 = ? WHERE user_id = ?", (qr_b64, user_id))
    conn.commit()
    conn.close()


def get_user_qr_by_account_id(account_id: int) -> str:
    """Fetch the QR code of the user who owns the given account ID."""
    # First get the user_id from the customers db
    c_conn = get_connection("customers")
    c_cursor = c_conn.cursor()
    c_cursor.execute("SELECT user_id FROM accounts WHERE account_id = ?", (account_id,))
    row = c_cursor.fetchone()
    c_conn.close()
    
    if not row:
        return ""
        
    user_id = row["user_id"]
    
    # Then get the qr_code_b64 from the managers db
    m_conn = get_connection("managers")
    m_cursor = m_conn.cursor()
    m_cursor.execute("SELECT qr_code_b64 FROM users WHERE user_id = ?", (user_id,))
    u_row = m_cursor.fetchone()
    m_conn.close()
    
    if not u_row or not u_row["qr_code_b64"]:
        return ""
        
    return u_row["qr_code_b64"]


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
    """Create a new bank account with a distinct 8-10 digit random account_id."""
    import random
    conn = get_connection("customers")
    cursor = conn.cursor()
    
    # Generate a unique 9-digit account number (100000000 to 999999999)
    while True:
        acc_id = random.randint(100000000, 999999999)
        cursor.execute("SELECT account_id FROM accounts WHERE account_id = ?", (acc_id,))
        if not cursor.fetchone():
            break
            
    cursor.execute(
        """INSERT INTO accounts (account_id, customer_name, email, phone, balance, account_type, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (acc_id, customer_name, email, phone, balance, account_type, user_id)
    )
    conn.commit()
    conn.close()
    return acc_id


def create_user_with_account(username: str, password_hash: str, role: str, full_name: str,
                              email: str, phone: str, account_type: str, balance: float) -> tuple:
    """
    Atomic creation of a user and their initial account (if role is customer).
    Since databases are separate, we handle rollback manually.
    """
    user_id = create_user(username, password_hash, role, full_name)
    if not user_id:
        raise Exception("Could not create user record")

    if role == 'customer':
        try:
            acc_id = create_account(full_name, email, phone, balance, account_type, user_id)
            return user_id, acc_id
        except Exception as e:
            # Rollback user creation
            delete_user(user_id)
            raise e
    
    return user_id, None


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
                    target_account_id: Optional[int] = None,
                    category: str = "General") -> int:
    """Record a transaction."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO transactions (account_id, txn_type, amount, category, description, status, target_account_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (account_id, txn_type, amount, category, description, status, target_account_id)
    )
    conn.commit()
    txn_id = cursor.lastrowid
    conn.close()
    return txn_id if txn_id is not None else 0


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

def update_transaction(txn_id: int, amount: float, category: str, description: str, txn_type: str):
    """Update a financial record (transaction)."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE transactions SET amount = ?, category = ?, description = ?, txn_type = ? WHERE txn_id = ?",
        (amount, category, description, txn_type, txn_id)
    )
    conn.commit()
    conn.close()

def delete_transaction(txn_id: int):
    """Delete a financial record."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE txn_id = ?", (txn_id,))
    conn.commit()
    conn.close()

def get_transactions_filtered(user_id=None, category=None, txn_type=None, start_date=None, end_date=None) -> list:
    """Get transactions with filters."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    
    query = "SELECT t.* FROM transactions t "
    params = []
    
    if user_id is not None:
        query += "JOIN accounts a ON t.account_id = a.account_id WHERE a.user_id = ? "
        params.append(user_id)
    else:
        query += "WHERE 1=1 "
        
    if category:
        query += "AND t.category = ? "
        params.append(category)
    if txn_type:
        query += "AND t.txn_type = ? "
        params.append(txn_type)
    if start_date:
        query += "AND date(t.timestamp) >= date(?) "
        params.append(start_date)
    if end_date:
        query += "AND date(t.timestamp) <= date(?) "
        params.append(end_date)
        
    query += "ORDER BY t.timestamp DESC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_dashboard_summary(user_id=None) -> dict:
    """Get summarized analytics for the dashboard."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    
    base_join = "JOIN accounts a ON t.account_id = a.account_id" if user_id else ""
    where_clause = "WHERE a.user_id = ?" if user_id else "WHERE 1=1"
    params = (user_id,) if user_id else ()
    
    # Total Income (deposits) & Total Expenses (withdrawals/transfers out)
    cursor.execute(f"SELECT SUM(amount) FROM transactions t {base_join} {where_clause} AND t.txn_type='deposit'", params)
    income_val = cursor.fetchone()[0]
    total_income = income_val if income_val else 0.0
    
    cursor.execute(f"SELECT SUM(amount) FROM transactions t {base_join} {where_clause} AND t.txn_type IN ('withdrawal', 'transfer')", params)
    expense_val = cursor.fetchone()[0]
    total_expenses = expense_val if expense_val else 0.0
    
    net_balance = total_income - total_expenses
    
    # Category totals
    cursor.execute(f"SELECT t.category, SUM(t.amount) as total FROM transactions t {base_join} {where_clause} GROUP BY t.category", params)
    categories = [{"category": r["category"], "total": r["total"]} for r in cursor.fetchall()]
    
    # Monthly Trends (last 6 months)
    cursor.execute(f"SELECT strftime('%Y-%m', t.timestamp) as month, SUM(CASE WHEN t.txn_type='deposit' THEN t.amount ELSE 0 END) as income, SUM(CASE WHEN t.txn_type IN ('withdrawal', 'transfer') THEN t.amount ELSE 0 END) as expense FROM transactions t {base_join} {where_clause} GROUP BY month ORDER BY month DESC LIMIT 6", params)
    monthly_trends = [{"month": r["month"], "income": r["income"], "expense": r["expense"]} for r in cursor.fetchall()]
    
    # Recent Activity (last 5)
    cursor.execute(f"SELECT t.* FROM transactions t {base_join} {where_clause} ORDER BY t.timestamp DESC LIMIT 5", params)
    recent = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
        "category_totals": categories,
        "monthly_trends": list(reversed(monthly_trends)),  # Chronological
        "recent_activity": recent
    }


# ─────────────────────────────────────────────
# BENEFICIARIES Operations (customers.db)
# ─────────────────────────────────────────────

def create_beneficiary(user_id: int, account_id: int, name: str) -> int:
    """Add a new saved beneficiary."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO beneficiaries (user_id, account_id, name) VALUES (?, ?, ?)",
        (user_id, account_id, name)
    )
    conn.commit()
    b_id = cursor.lastrowid
    conn.close()
    return b_id if b_id is not None else 0


def get_beneficiaries(user_id: int) -> list:
    """Get all beneficiaries for a specific user."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM beneficiaries WHERE user_id = ? ORDER BY name ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_beneficiary(user_id: int, beneficiary_id: int):
    """Delete a beneficiary (ensuring it belongs to the user)."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM beneficiaries WHERE ben_id = ? AND user_id = ?", (beneficiary_id, user_id))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# SECURITY ALERTS Operations (customers.db)
# ─────────────────────────────────────────────

def create_security_alert(user_id: int, message: str, alert_type: str = "info") -> int:
    """Create a new security alert for a user."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO security_alerts (user_id, message, type) VALUES (?, ?, ?)",
        (user_id, message, alert_type)
    )
    conn.commit()
    a_id = cursor.lastrowid
    conn.close()
    return a_id if a_id is not None else 0


def get_unread_alerts(user_id: int) -> list:
    """Get all unread security alerts for a user."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM security_alerts WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_alert_read(user_id: int, alert_id: int):
    """Mark a specific alert as read."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE security_alerts SET is_read = 1 WHERE id = ? AND user_id = ?", (alert_id, user_id))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# ACTIVE LOANS Operations (customers.db)
# ─────────────────────────────────────────────

def create_active_loan(account_id: int, principal: float, interest_rate: float,
                       term_months: int, total_cost: float, emi: float) -> int:
    """Record a newly approved active loan."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO active_loans 
           (account_id, principal, interest_rate, term_months, total_cost_with_interest, remaining_balance, next_emi_amount)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (account_id, principal, interest_rate, term_months, total_cost, total_cost, emi)
    )
    conn.commit()
    l_id = cursor.lastrowid
    conn.close()
    return l_id if l_id is not None else 0


def get_active_loans_by_account(account_id: int) -> list:
    """Get all active loans for a specific account."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_loans WHERE account_id = ? AND remaining_balance > 0 ORDER BY created_at DESC", (account_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_loan_by_id(loan_id: int) -> Optional[dict]:
    """Get a specific active loan."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_loans WHERE loan_id = ?", (loan_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_loan_balance(loan_id: int, new_balance: float):
    """Update the remaining balance of an active loan (legacy)."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE active_loans SET remaining_balance = ? WHERE loan_id = ?", (new_balance, loan_id))
    conn.commit()
    conn.close()

def record_loan_emi_payment(loan_id: int, amount_paid: float):
    """Record an EMI payment incrementally onto a loan and auto-close if paid off."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE loans SET total_paid = total_paid + ? WHERE loan_id = ?", (amount_paid, loan_id))
    # Check if fully paid off (Total + Interest - 0.1 for floating point safety)
    cursor.execute("UPDATE loans SET status = 'paid' WHERE loan_id = ? AND total_paid >= (emi_amount * tenure_months) - 0.1", (loan_id,))
    conn.commit()
    conn.close()


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
    return req_id if req_id is not None else 0


def get_pending_requests() -> list:
    """Get all requests pending accountant approval, excluding loans."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pending_requests WHERE status = 'pending' AND request_type != 'loan' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_manager_requests() -> list:
    """Get all requests pending manager approval, excluding loans."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pending_requests WHERE status = 'pending_manager' AND request_type != 'loan' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_customer_loans(customer_user_id: int) -> list:
    """Get all loan requests for a specific customer."""
    # First get customer's accounts
    accounts = get_accounts_by_user(customer_user_id)
    if not accounts:
        return []
        
    account_ids = [a['account_id'] for a in accounts]
    placeholders = ','.join(['?'] * len(account_ids))
    
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute(f'''
        SELECT * FROM pending_requests 
        WHERE request_type = 'loan' AND account_id IN ({placeholders})
        ORDER BY created_at DESC
    ''', tuple(account_ids))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pending_accountant_loans() -> list:
    """Get all loan requests pending accountant approval."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pending_requests WHERE status = 'pending' AND request_type = 'loan' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pending_manager_loans() -> list:
    """Get all loan requests pending manager approval."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pending_requests WHERE status = 'pending_manager' AND request_type = 'loan' ORDER BY created_at DESC")
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

def add_audit_log(action: str, performed_by: str, account_id: Optional[int] = None, details: str = ""):
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

def get_audit_logs_by_user(username: str, limit: int = 50) -> list:
    """Get audit logs for a specific user."""
    conn = get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log WHERE performed_by = ? ORDER BY timestamp DESC LIMIT ?", (username, limit))
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


def create_branch(branch_name: str, location: str, manager_id: Optional[int] = None) -> int:
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
    return bid if bid is not None else 0


def update_branch(branch_id: int, branch_name: str, location: str, manager_id: Optional[int] = None):
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

# ─────────────────────────────────────────────
# NOTIFICATIONS (managers.db)
# ─────────────────────────────────────────────

def add_notification(user_id: int, message: str, notif_type: str = "info"):
    """Send a notification to a specific user (in managers.db)."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
        (user_id, message, notif_type)
    )
    conn.commit()
    conn.close()


def notify_staff(message: str, roles: Optional[list] = None, notif_type: str = "info"):
    """Send a notification to all users with specific roles (default: accountant, manager)."""
    if roles is None:
        roles = ["accountant", "manager"]
        
    conn = get_connection("managers")
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(roles))
    cursor.execute(f"SELECT user_id FROM users WHERE role IN ({placeholders}) AND is_active = 1", tuple(roles))
    staff_users = cursor.fetchall()
    
    for u in staff_users:
        cursor.execute(
            "INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
            (u["user_id"], message, notif_type)
        )
    conn.commit()
    conn.close()


def get_notifications(user_id: int, limit: int = 20):
    """Get recent notifications for a user."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# TICKETING API
# ─────────────────────────────────────────────

def create_ticket(user_id: int, subject: str) -> int:
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO support_tickets (user_id, subject) VALUES (?, ?)", (user_id, subject))
    conn.commit()
    t_id = cursor.lastrowid
    conn.close()
    return t_id if t_id else 0

def get_tickets_by_user(user_id: int) -> list:
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM support_tickets WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_notification_read(notif_id: int):
    """Mark a notification as read."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE notif_id = ?", (notif_id,))
    conn.commit()
    conn.close()


def mark_all_notifications_read(user_id: int):
    """Mark all notifications for a user as read."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_unread_notification_count(user_id: int) -> int:
    """Get the count of unread notifications for a user."""
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# --- QR Code Functions ---

def update_account_qr(account_id: int, qr_data: str):
    """Update the QR code for a specific account."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET qr_code = ? WHERE account_id = ?", (qr_data, account_id))
    conn.commit()
    conn.close()

def get_account_qr(account_id: int) -> str:
    """Get the QR code for a specific account."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT qr_code FROM accounts WHERE account_id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()
    return str(row[0]) if row and row[0] else ""


# ─────────────────────────────────────────────
# BENEFICIARIES (customers.db)
# ─────────────────────────────────────────────

def add_beneficiary(user_id: int, name: str, account_id: int, nickname: str = ""):
    """Add a new beneficiary for a user."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO beneficiaries (user_id, name, account_id, nickname) VALUES (?, ?, ?, ?)",
        (user_id, name, account_id, nickname)
    )
    conn.commit()
    conn.close()


def get_beneficiaries(user_id: int):
    """Get all beneficiaries for a user."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM beneficiaries WHERE user_id = ? ORDER BY name", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_tickets() -> list:
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM support_tickets ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_beneficiary(ben_id: int):
    """Delete a beneficiary by ID."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM beneficiaries WHERE ben_id = ?", (ben_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# LOANS (customers.db)
# ─────────────────────────────────────────────

def apply_loan(user_id: int, account_id: int, amount: float, tenure: int, emi: float):
    """Apply for a new loan."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO loans (user_id, account_id, loan_amount, tenure_months, emi_amount) VALUES (?, ?, ?, ?, ?)",
        (user_id, account_id, amount, tenure, emi)
    )
    conn.commit()
    conn.close()


def get_loans_by_user(user_id: int):
    """Get all loans for a specific user."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loans WHERE user_id = ? ORDER BY applied_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_ticket_messages(ticket_id: int) -> list:
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_loans():
    """Get all loans (any user)."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loans ORDER BY applied_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_ticket_message(ticket_id: int, sender_user_id: int, message: str) -> int:
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ticket_messages (ticket_id, sender_user_id, message) VALUES (?, ?, ?)",
                   (ticket_id, sender_user_id, message))
    cursor.execute("UPDATE support_tickets SET updated_at = datetime('now','localtime') WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    m_id = cursor.lastrowid
    conn.close()
    return m_id if m_id else 0

def update_ticket_status(ticket_id: int, status: str):
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE support_tickets SET status = ?, updated_at = datetime('now','localtime') WHERE ticket_id = ?", (status, ticket_id))
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# CREDIT CARDS API
# ─────────────────────────────────────────────

def create_credit_card(account_id: int, limit: float, apr: float) -> int:
    import random
    card_number = f"4000{random.randint(100000000000, 999999999999)}"
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO credit_cards (account_id, card_number, credit_limit, apr) VALUES (?, ?, ?, ?)",
                   (account_id, card_number, limit, apr))
    conn.commit()
    c_id = cursor.lastrowid
    conn.close()
    return c_id if c_id else 0

def get_credit_cards_by_account(account_id: int) -> list:
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM credit_cards WHERE account_id = ? AND status = 'active'", (account_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_loan_by_id(loan_id: int):
    """Get a single loan by ID."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loans WHERE loan_id = ?", (loan_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_credit_card_balance(card_id: int, new_balance: float):
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE credit_cards SET current_balance = ? WHERE card_id = ?", (new_balance, card_id))
    conn.commit()
    conn.close()

def get_credit_card_by_id(card_id: int) -> Optional[dict]:
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM credit_cards WHERE card_id = ?", (card_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_loan_status(loan_id: int, status: str, approved_by: str, accountant_status: str = "", manager_status: str = ""):
    """Update a loan's status (approved/rejected)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection("customers")
    cursor = conn.cursor()
    
    if accountant_status:
        cursor.execute("UPDATE loans SET accountant_status = ? WHERE loan_id = ?", (accountant_status, loan_id))
    if manager_status:
        cursor.execute("UPDATE loans SET manager_status = ? WHERE loan_id = ?", (manager_status, loan_id))
        
    cursor.execute(
        "UPDATE loans SET status = ?, approved_by = ?, approved_at = ? WHERE loan_id = ?",
        (status, approved_by, now, loan_id)
    )
    conn.commit()
    conn.close()


def make_emi_payment(loan_id: int, amount: float):
    """Record an EMI payment for a loan."""
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("UPDATE loans SET total_paid = total_paid + ? WHERE loan_id = ?", (amount, loan_id))
    # If total_paid >= (emi * tenure) - rough closing logic
    cursor.execute("SELECT emi_amount, tenure_months, total_paid FROM loans WHERE loan_id = ?", (loan_id,))
    loan = cursor.fetchone()
    if loan and loan['total_paid'] >= (loan['emi_amount'] * loan['tenure_months']):
        cursor.execute("UPDATE loans SET status = 'closed' WHERE loan_id = ?", (loan_id,))
    conn.commit()
    conn.close()

def get_all_credit_cards() -> list:
    conn = get_connection("customers")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM credit_cards ORDER BY card_id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user_avatar(user_id: int, avatar_b64: str):
    conn = get_connection("managers")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET avatar_b64 = ? WHERE user_id = ?", (avatar_b64, user_id))
    conn.commit()
    conn.close()
    conn.commit()
    conn.close()

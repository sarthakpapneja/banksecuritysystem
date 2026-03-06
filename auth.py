"""
Bank Security System - Authentication & Authorization
Handles login, password hashing, session management, and permission checking.
"""

import hashlib
import os
from typing import Optional
from models import Role
import db_manager


# ─────────────────────────────────────────────
# Password Hashing
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password with SHA-256 + salt."""
    salt = "bank_security_salt_2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == password_hash


# ─────────────────────────────────────────────
# Session Management
# ─────────────────────────────────────────────

class Session:
    """Tracks the currently logged-in user."""

    def __init__(self):
        self.user: Optional[dict] = None
        self.is_authenticated: bool = False

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """
        Attempt to log in. Returns (success, message).
        """
        user = db_manager.get_user_by_username(username)

        if not user:
            return False, "User not found."

        if not user["is_active"]:
            return False, "Account is deactivated. Contact your manager."

        if not verify_password(password, user["password_hash"]):
            # Log failed attempt
            db_manager.add_system_log("LOGIN_FAILED", user["user_id"], f"Failed login attempt for '{username}'")
            return False, "Incorrect password."

        self.user = user
        self.is_authenticated = True

        # Log successful login
        db_manager.add_system_log("LOGIN_SUCCESS", user["user_id"], f"User '{username}' logged in")
        db_manager.add_audit_log("LOGIN", username, details=f"Role: {user['role']}")

        return True, f"Welcome, {user['full_name']}!"

    def logout(self):
        """Log out the current user."""
        if self.user:
            db_manager.add_system_log("LOGOUT", self.user["user_id"], f"User '{self.user['username']}' logged out")
        self.user = None
        self.is_authenticated = False

    @property
    def role(self) -> Optional[str]:
        """Get the current user's role."""
        return self.user["role"] if self.user else None

    @property
    def username(self) -> Optional[str]:
        """Get the current user's username."""
        return self.user["username"] if self.user else None

    @property
    def user_id(self) -> Optional[int]:
        """Get the current user's ID."""
        return self.user["user_id"] if self.user else None

    @property
    def full_name(self) -> Optional[str]:
        """Get the current user's full name."""
        return self.user["full_name"] if self.user else None


# ─────────────────────────────────────────────
# Permission Checking
# ─────────────────────────────────────────────

# Define which roles can access which features
PERMISSIONS = {
    "view_own_balance":       [Role.CUSTOMER.value, Role.MANAGER.value],
    "deposit":                [Role.CUSTOMER.value, Role.MANAGER.value],
    "withdraw":               [Role.CUSTOMER.value, Role.MANAGER.value],
    "transfer":               [Role.CUSTOMER.value, Role.MANAGER.value],
    "view_own_transactions":  [Role.CUSTOMER.value, Role.MANAGER.value],
    "view_all_transactions":  [Role.ACCOUNTANT.value, Role.MANAGER.value],
    "approve_requests":       [Role.ACCOUNTANT.value, Role.MANAGER.value],
    "create_account":         [Role.ACCOUNTANT.value, Role.MANAGER.value],
    "close_account":          [Role.ACCOUNTANT.value, Role.MANAGER.value],
    "view_audit_logs":        [Role.ACCOUNTANT.value, Role.MANAGER.value],
    "manage_users":           [Role.MANAGER.value],
    "view_system_logs":       [Role.MANAGER.value],
    "generate_reports":       [Role.MANAGER.value],
    "view_all_accounts":      [Role.ACCOUNTANT.value, Role.MANAGER.value],
}


def has_permission(session: Session, permission: str) -> bool:
    """Check if the current user has a specific permission."""
    if not session.is_authenticated or not session.role:
        return False
    allowed_roles = PERMISSIONS.get(permission, [])
    return session.role in allowed_roles


def require_permission(session: Session, permission: str) -> bool:
    """
    Check permission and return True/False. Prints a message if denied.
    Used by the UI layer.
    """
    if not has_permission(session, permission):
        return False
    return True

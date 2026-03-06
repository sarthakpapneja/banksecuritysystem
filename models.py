"""
Bank Security System - Data Models
Defines dataclasses for all entities in the banking system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Role(Enum):
    CUSTOMER = "customer"
    ACCOUNTANT = "accountant"
    MANAGER = "manager"


class AccountType(Enum):
    SAVINGS = "savings"
    CURRENT = "current"
    FIXED_DEPOSIT = "fixed_deposit"


class TransactionType(Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"


class TransactionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class RequestType(Enum):
    ACCOUNT_OPEN = "account_open"
    ACCOUNT_CLOSE = "account_close"
    LARGE_WITHDRAWAL = "large_withdrawal"
    LARGE_TRANSFER = "large_transfer"


@dataclass
class User:
    user_id: int
    username: str
    password_hash: str
    role: Role
    full_name: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class Account:
    account_id: int
    customer_name: str
    email: str
    phone: str
    balance: float
    account_type: AccountType
    user_id: int
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class Transaction:
    txn_id: int
    account_id: int
    txn_type: TransactionType
    amount: float
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""
    status: TransactionStatus = TransactionStatus.COMPLETED
    target_account_id: Optional[int] = None


@dataclass
class PendingRequest:
    request_id: int
    account_id: int
    request_type: RequestType
    amount: float
    status: TransactionStatus = TransactionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    processed_by: Optional[str] = None
    details: str = ""


@dataclass
class AuditLog:
    log_id: int
    action: str
    performed_by: str
    account_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    details: str = ""


@dataclass
class SystemLog:
    log_id: int
    action: str
    user_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    ip_address: str = "127.0.0.1"
    details: str = ""


@dataclass
class BranchInfo:
    branch_id: int
    branch_name: str
    location: str
    manager_id: Optional[int] = None

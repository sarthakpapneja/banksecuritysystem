<div align="center">

# 🏦 Bank Security System

**A secure, role-based banking management system with a modern web UI and CLI interface.**

Built with Python · Flask · SQLite · Vanilla JS

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<br>

<img src="https://raw.githubusercontent.com/sarthakpapneja/banksecuritysystem/main/screenshots/login.png" alt="Login Page" width="700">

</div>

---

## ✨ Features

### 🔐 Role-Based Access Control (RBAC)

Three-tiered permission system with complete data segregation across dedicated databases:

| Role | Capabilities |
|------|-------------|
| **👤 Customer** | View balance, deposit, withdraw, transfer funds, view statements |
| **📋 Accountant** | Process approval requests, view all accounts & transactions, create accounts, audit log |
| **👑 Manager** | Bank reports, user management (CRUD), system logs + all accountant features |

### 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Presentation Layer                     │
│         Web UI (Flask + SPA)  ·  Rich CLI (main.py)      │
├──────────────────────────────────────────────────────────┤
│                  Authentication Layer                     │
│          SHA-256 Hashing  ·  Session Management           │
│              Role-Based Permission Guards                 │
├──────────────────────────────────────────────────────────┤
│                   Business Logic Layer                    │
│           db_manager.py  ·  models.py  ·  auth.py        │
├────────────────┬─────────────────┬───────────────────────┤
│  customers.db  │  accountants.db │    managers.db        │
│  ───────────── │  ────────────── │  ──────────────       │
│  • accounts    │  • requests     │  • users              │
│  • transactions│  • audit_log    │  • system_logs        │
│                │                 │  • branch_info        │
└────────────────┴─────────────────┴───────────────────────┘
```

### 🎨 Modern Web UI

- **Dark glassmorphism** aesthetic with gradient accents
- **Responsive SPA** — sidebar navigation, stat cards, data tables
- **Real-time** toast notifications and modal dialogs
- **Quick login** shortcuts for all demo roles
- One-click approve/reject for pending requests

### 💻 Rich CLI

- Polished terminal interface using the `rich` library
- Full feature parity with the web UI
- Color-coded outputs, formatted tables, and interactive prompts

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/sarthakpapneja/banksecuritysystem.git
cd banksecuritysystem

# Install dependencies
pip install -r requirements.txt

# Seed demo data
python3 seed_data.py
```

### Run

```bash
# 🌐 Web UI (recommended)
python3 server.py
# Open http://localhost:5001

# 💻 CLI version
python3 main.py
```

### Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| 👤 Customer | `john_doe` | `password123` |
| 👤 Customer | `jane_doe` | `password123` |
| 📋 Accountant | `acc_smith` | `password123` |
| 📋 Accountant | `acc_jones` | `password123` |
| 👑 Manager | `mgr_admin` | `admin123` |
| 👑 Manager | `mgr_lead` | `admin123` |

---

## 📁 Project Structure

```
bank_security_system/
├── server.py          # Flask API server (web UI backend)
├── main.py            # Rich CLI application
├── db_manager.py      # Database operations for all 3 databases
├── auth.py            # Authentication & session management
├── models.py          # Data models & enums
├── seed_data.py       # Demo data population script
├── requirements.txt   # Python dependencies
├── static/
│   ├── index.html     # Single-page web application
│   └── style.css      # Dark theme stylesheet
└── data/              # Auto-generated database directory
    ├── customers.db   # Accounts & transactions
    ├── accountants.db # Pending requests & audit logs
    └── managers.db    # Users, system logs & branches
```

---

## 🗄️ Database Schema

### customers.db
| Table | Columns |
|-------|---------|
| `accounts` | account_id, customer_name, email, phone, balance, account_type, is_active, user_id, created_at |
| `transactions` | txn_id, account_id, txn_type, amount, description, status, related_account, timestamp |

### accountants.db
| Table | Columns |
|-------|---------|
| `pending_requests` | request_id, account_id, request_type, amount, details, status, created_at, processed_by |
| `audit_log` | log_id, action, performed_by, account_id, timestamp, details |

### managers.db
| Table | Columns |
|-------|---------|
| `users` | user_id, username, password_hash, role, full_name, is_active, created_at |
| `system_logs` | log_id, action, user_id, timestamp, details |
| `branch_info` | branch_id, branch_name, location, manager_id |

---

## 🔒 Security Features

- **Password Hashing** — SHA-256 with no plaintext storage
- **Session-Based Auth** — Flask server-side sessions
- **Role Guards** — Decorator-based route protection (`@role_required`)
- **Data Segregation** — Customer data, operations data, and admin data in separate databases
- **Audit Trail** — Every action logged with timestamp, user, and details
- **Large Transaction Controls** — Withdrawals/transfers ≥ ₹5,000 require accountant approval

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask 3.0 |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Database | SQLite3 (3 separate databases) |
| CLI | Rich, Tabulate |
| Auth | SHA-256 (hashlib) |

---

## 📝 API Endpoints

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/api/login` | All | Authenticate user |
| POST | `/api/logout` | All | End session |
| GET | `/api/accounts` | All | List accounts (scoped by role) |
| POST | `/api/deposit` | Customer, Manager | Deposit funds |
| POST | `/api/withdraw` | Customer, Manager | Withdraw funds |
| POST | `/api/transfer` | Customer, Manager | Transfer between accounts |
| GET | `/api/requests` | Accountant, Manager | View pending requests |
| POST | `/api/requests/:id/process` | Accountant, Manager | Approve/reject request |
| GET | `/api/audit-logs` | Accountant, Manager | View audit trail |
| GET | `/api/report` | Manager | Generate bank report |
| GET | `/api/users` | Manager | List all users |
| POST | `/api/users/create` | Manager | Create new user |
| DELETE | `/api/users/:id` | Manager | Delete user |
| GET | `/api/system-logs` | Manager | View system events |

---

## 📄 License

This project is licensed under the MIT License.

---

<div align="center">

**Made with ❤️ by [Sarthak Papneja](https://github.com/sarthakpapneja)**

</div>

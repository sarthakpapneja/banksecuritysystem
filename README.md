<div align="center">

# ZenRupee - Secure Bank & Finance Platform

**A secure, structured backend engineered to handle banking operations, financial data processing, role-based access control, and dynamic dashboard summaries.**

Built with Python · Flask · SQLite

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<br>
</div>

---

## Overview

ZenRupee is a robust **Finance Data Processing and Access Control Platform** designed to securely handle banking records, execute complex access constraints based on user roles, and generate real-time financial analytics. 

It satisfies rigorous backend engineering standards by enforcing rigid data segregation, providing comprehensive financial record CRUD capabilities, supporting multi-layered Role-Based Access Control (RBAC), and resolving structural operations safely using lightweight SQL transactions.

---

## Technical Design & Architecture

### 1. Unified Backend Design & Separation of Concerns
The application follows a clear service-driven structure:
- **`server.py`:** Handles network delivery, routing constraints, HTTP parsing, and session injections. It is completely isolated from database queries.
- **`db_manager.py`:** Acts as the dedicated ORM and persistence layer, encapsulating all SQLite execution schemas and returning dictionary payloads securely.
- **`auth.py` & `models.py`:** Abstracted components focusing solely on hash generation and data entity structuring.

### 2. Physical Data Modeling (3-Tier Segregation)
Rather than a single monolithic database containing highly sensitive information beside application logs, the persistence layer utilizes three strictly isolated SQLite files:
- **`customers.db`**: Houses user relationships, financial records/transactions, and dynamic active loans. Kept clean from admin log pollution.
- **`accountants.db`**: Dedicated to buffering pending transaction requests needing human oversight.
- **`managers.db`**: Handles absolute source-of-truth user identities, encrypted credentials, explicit system logs, and RBAC assignment.

### 3. Reliability, Validation, & Access Control
- **Input Validation:** Numeric endpoints (transfers/loans/withdrawals) rigorously cast input against floating-point boundary conditions, throwing HTTP 400 immediately on negative or irregular balances.
- **Role Enforcement Contexts:** Critical REST API endpoints are decorated with custom `@role_required("manager", "accountant")` context interceptors.
- **Transaction Safety:** Failed auth attempts sequentially lock out the API bounds temporarily. EMI operations and transaction deletions utilize secure balance sweeps to ensure ledgers remain completely synchronous.

### 4. Mathematical Logic for Loans & Analytics
- **Live Dashboards:** Aggregation engines inside `GET /api/dashboard/summary` dynamically resolve floating sums grouping 'Income' against 'Expense' across categories, circumventing frontend mathematical strain.
- **Automated Repayment Closures:** Complex loan equations trace accured interest accurately (`EMI * Tenure`) over basic principal tracking. Loans execute auto-closing logic natively against `active` statuses on final EMI resolution points.

---

## Assumptions & Trade-offs

1. **SQLite Over PostgreSQL:** 
   SQLite was strictly selected for demonstration portability and environment simplicity. Since the platform architecture abstracts executing connections inside `db_manager`, migrating to a distributed PostgreSQL instance requires almost zero adjustments to business logic.
2. **Session-Level Authentication vs JWT:** 
   Currently, the system isolates security via server-signed persistent memory sessions rather than JWTs. This limits massive horizontal cross-origin scaling but ensures perfect deterministic control over explicit session termination and user state invalidation server-side.
3. **Soft vs Hard Deletes:** 
   Transactions are directly mutable and deletable manually by Managers to satisfy complete CRUD capabilities, though an enterprise implementation would force fully immutable Append-Only immutable logs.

---

## Quick Start Guide

### Prerequisites
- Python 3.10+
- Native pip

### Local Setup

```bash
# Clone the repository
git clone https://github.com/sarthakpapneja/ZenRupee.git
cd ZenRupee

# Install lightweight dependencies
pip install -r requirements.txt

# Seed the environment with testing data schemas
python3 seed_data.py
```

### Running the Environment

Boot the Flask API engine directly on `http://localhost:5005`:

```bash
python3 server.py
```

### Sandbox Accounts

| Role | Environment Login | Password | Access Constraints |
|------|----------|----------|-------------------|
| Customer | `john_doe` | `password123` | Personal records only, restricted API surface focus. |
| Accountant | `acc_smith` | `password123` | Read-only ledger audit access, approval clearance. |
| Manager | `mgr_admin` | `admin123` | Read/Write absolute authority routing across systems. |

---

## API Structural Highlights

| Method | Component Path | Minimum Role Required | Logic Functionality |
|--------|----------|------|-------------|
| **GET**  | `/api/dashboard/summary` | *All* (Dynamic scoping) | Calculates aggregate net margins, trends, and localized categorical arrays. |
| **GET**  | `/api/transactions` | *All* | Retrieves records with optional `category` grouping. |
| **POST** | `/api/loan/pay` | Customer | Analyzes explicit account limits, sweeps EMI funds, evaluates interest arrays, and conditionally halts loans upon maturity completion. |
| **POST** | `/api/transactions` | Manager | Explicitly inserts new unbuffered records natively. |
| **PUT**  | `/api/transactions/:id` | Manager | Updates categorizations and financial values post-factum. |
| **DELETE**| `/api/transactions/:id` | Manager | Forces hard removals against the schema mapping. |
| **POST** | `/api/requests/:id/process` | Accountant / Manager | Unlocks queue buffers into the main transaction pipeline. |

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for more information (2026).

<div align="center">
<b>Made by Sarthak Papneja</b>
</div>

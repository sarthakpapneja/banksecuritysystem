# ZenRupee API Reference (2026)

This document provides a comprehensive list of all API endpoints available in the ZenRupee platform.

## Authentication & Session
| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/login` | Public | Authenticates user; returns session cookie. |
| `POST` | `/api/logout` | All | Invalidates current session. |
| `GET` | `/api/me` | All | Returns profile of current logged-in user. |
| `POST` | `/api/change-password` | All | Updates user password (requires old password). |

## Account & Transaction Management
| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/accounts` | Customer | Lists all accounts owned by current customer. |
| `GET` | `/api/accounts` | Staff | Lists all accounts in the system (all customers). |
| `GET` | `/api/accounts/<id>` | All | Fetches specific account details. |
| `GET` | `/api/accounts/lookup/<no>`| All | Finds account details by account number. |
| `GET` | `/api/accounts/<id>/statement`| All | Generates HTML Mini-Statement. |
| `POST` | `/api/deposit` | Staff | Direct deposit into a customer account. |
| `POST` | `/api/withdraw` | Staff | Direct withdrawal from a customer account. |
| `POST` | `/api/transfer` | Customer | Fund transfer between accounts. |
| `GET` | `/api/transactions` | All | Lists transactions (filtered by query params). |
| `GET` | `/api/transactions/all` | Staff | Full system transaction history. |
| `GET` | `/api/transactions/<id>/receipt`| All | Generates HTML Transaction Receipt. |
| `DELETE`| `/api/transactions/<id>` | Manager | Deletes a transaction record. |

## Credit Cards
| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/credit_cards` | All | Lists active credit cards. |
| `POST` | `/api/credit_cards/apply` | Customer | Requests a new credit card from management. |
| `POST` | `/api/credit_cards/pay` | Customer | Pays off credit card balance from bank account. |
| `POST` | `/api/credit_cards/charge` | Customer | Simulate a charge on the credit card. |

## Loans
| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/active_loans` | Customer | Lists current active loans for user. |
| `GET` | `/api/loans` | Staff | Lists all pending/active loan applications. |
| `POST` | `/api/loans/apply` | Customer | Submits a new loan application. |
| `POST` | `/api/loans/<id>/accountant-review`| Accountant | Marks loan for manager approval. |
| `POST` | `/api/loans/<id>/approve` | Manager | Final approval and disbursement of loan funds. |
| `POST` | `/api/loan/pay` | Customer | Pays a standard EMI for a loan. |

## Support & Tickets
| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/tickets` | All | Lists support tickets (Own if Customer, All if Staff). |
| `POST` | `/api/tickets` | Customer | Opens a new support ticket. |
| `GET` | `/api/tickets/<id>/messages`| All | Fetches conversation history for a ticket. |
| `POST` | `/api/tickets/<id>/messages`| All | Adds a reply to a support ticket. |
| `POST` | `/api/tickets/<id>/close` | Staff | Closes a resolved support ticket. |

## User & Staff Management
| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/users` | Staff | Lists all system users. |
| `GET` | `/api/users/<id>/details` | Staff | Deep-dive profile for a specific customer. |
| `POST` | `/api/users/create` | Manager | Instantly create a new user/staff member. |
| `POST` | `/api/users/request-create`| Accountant | Submit user for manager approval. |
| `POST` | `/api/users/<id>/toggle` | Staff | Enable/Disable user account. |
| `POST` | `/api/users/<id>/unlock` | Staff | Manually unlock account (after failed logins). |
| `DELETE`| `/api/users/<id>` | Manager | Permanently deletes a user. |

## Meta & System
| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/dashboard/summary` | All | Returns aggregate stats for dashboard UI. |
| `GET` | `/api/audit-log` | Manager | Fetches full system audit trails. |
| `GET` | `/api/system-logs` | Staff | Fetches technical system logs (logins, IP, etc). |
| `GET` | `/api/branches` | All | Lists bank branch locations and managers. |
| `POST` | `/api/branches` | Manager | Creates a new physical bank branch. |
| `GET` | `/api/alerts` | Customer | Fetches unread notifications/alerts. |
| `POST` | `/api/alerts/<id>/read` | Customer | Marks a specific alert as read. |

---
*Note: All endpoints require a valid session cookie. Endpoints marked with specific roles require that role in the session.*

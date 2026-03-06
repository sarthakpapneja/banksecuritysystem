"""
Bank Security System - Main Application
A comprehensive CLI banking application with Role-Based Access Control.
Uses Rich library for a polished terminal interface.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm
from rich.text import Text
from rich.columns import Columns
from rich import box
from rich.align import Align
from rich.rule import Rule

import db_manager
import auth
from auth import Session, has_permission

console = Console()

# Large withdrawal/transfer threshold that triggers accountant review
LARGE_AMOUNT_THRESHOLD = 5000.00


# ═══════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def show_banner():
    banner = """
╔══════════════════════════════════════════════════╗
║        🏦  BANK SECURITY SYSTEM  🏦             ║
║     Secure · Reliable · Role-Based Access        ║
╚══════════════════════════════════════════════════╝
    """
    console.print(Panel(banner.strip(), style="bold cyan", box=box.DOUBLE))


def show_role_badge(session: Session):
    """Display the current user's role as a colored badge."""
    role_colors = {"customer": "green", "accountant": "yellow", "manager": "red"}
    color = role_colors.get(session.role, "white")
    console.print(
        Panel(
            f"[bold {color}]👤 {session.full_name}[/]  |  "
            f"Role: [bold {color}]{session.role.upper()}[/]  |  "
            f"Username: {session.username}",
            style=color,
            box=box.ROUNDED,
        )
    )


def pause():
    console.print("\n[dim]Press Enter to continue...[/]")
    input()


def show_access_denied():
    console.print("[bold red]🚫 ACCESS DENIED[/] — You don't have permission for this action.\n")


# ═══════════════════════════════════════════════
# LOGIN SCREEN
# ═══════════════════════════════════════════════

def login_screen() -> Session:
    """Display the login prompt and authenticate the user."""
    session = Session()

    while True:
        clear_screen()
        show_banner()
        console.print(Rule("🔐 Login", style="cyan"))
        console.print()

        username = Prompt.ask("[bold cyan]Username[/]")
        password = Prompt.ask("[bold cyan]Password[/]", password=True)

        success, message = session.login(username, password)

        if success:
            console.print(f"\n[bold green]✅ {message}[/]")
            console.print(f"[dim]Logged in as [bold]{session.role.upper()}[/][/]")
            pause()
            return session
        else:
            console.print(f"\n[bold red]❌ {message}[/]")
            retry = Confirm.ask("Try again?", default=True)
            if not retry:
                console.print("[yellow]Goodbye! 👋[/]")
                sys.exit(0)


# ═══════════════════════════════════════════════
# CUSTOMER FEATURES
# ═══════════════════════════════════════════════

def customer_view_balance(session: Session):
    """View the customer's account balances."""
    accounts = db_manager.get_accounts_by_user(session.user_id)

    if not accounts:
        console.print("[yellow]No accounts found.[/]")
        return

    table = Table(title="💰 Your Accounts", box=box.ROUNDED, show_lines=True)
    table.add_column("Acc #", style="cyan", justify="center")
    table.add_column("Type", style="magenta")
    table.add_column("Balance (₹)", style="green", justify="right")
    table.add_column("Status", justify="center")

    total = 0.0
    for acc in accounts:
        status = "[green]Active[/]" if acc["is_active"] else "[red]Closed[/]"
        table.add_row(
            str(acc["account_id"]),
            acc["account_type"].upper(),
            f"{acc['balance']:,.2f}",
            status,
        )
        total += acc["balance"]

    console.print(table)
    console.print(f"\n[bold green]   Total Balance: ₹{total:,.2f}[/]\n")


def customer_deposit(session: Session):
    """Deposit money into an account."""
    accounts = db_manager.get_accounts_by_user(session.user_id)
    if not accounts:
        console.print("[yellow]No accounts found.[/]")
        return

    customer_view_balance(session)

    acc_id = IntPrompt.ask("[cyan]Enter Account #[/]")
    account = db_manager.get_account_by_id(acc_id)

    if not account or account["user_id"] != session.user_id:
        console.print("[red]Invalid account or access denied.[/]")
        return

    amount = FloatPrompt.ask("[cyan]Deposit Amount (₹)[/]")
    if amount <= 0:
        console.print("[red]Amount must be positive.[/]")
        return

    new_balance = account["balance"] + amount
    db_manager.update_balance(acc_id, new_balance)
    db_manager.add_transaction(acc_id, "deposit", amount, f"Cash deposit by {session.username}")
    db_manager.add_audit_log("DEPOSIT", session.username, acc_id, f"₹{amount:,.2f} deposited")

    console.print(f"\n[bold green]✅ ₹{amount:,.2f} deposited successfully![/]")
    console.print(f"[green]   New Balance: ₹{new_balance:,.2f}[/]\n")


def customer_withdraw(session: Session):
    """Withdraw money from an account."""
    accounts = db_manager.get_accounts_by_user(session.user_id)
    if not accounts:
        console.print("[yellow]No accounts found.[/]")
        return

    customer_view_balance(session)

    acc_id = IntPrompt.ask("[cyan]Enter Account #[/]")
    account = db_manager.get_account_by_id(acc_id)

    if not account or account["user_id"] != session.user_id:
        console.print("[red]Invalid account or access denied.[/]")
        return

    amount = FloatPrompt.ask("[cyan]Withdrawal Amount (₹)[/]")
    if amount <= 0:
        console.print("[red]Amount must be positive.[/]")
        return

    if amount > account["balance"]:
        console.print("[red]Insufficient balance![/]")
        return

    # Large withdrawals require accountant approval
    if amount >= LARGE_AMOUNT_THRESHOLD:
        console.print(f"[yellow]⚠ Withdrawals ≥ ₹{LARGE_AMOUNT_THRESHOLD:,.2f} require accountant approval.[/]")
        db_manager.create_request(acc_id, "large_withdrawal", amount, f"Requested by {session.username}")
        db_manager.add_audit_log("WITHDRAWAL_REQUEST", session.username, acc_id, f"₹{amount:,.2f} — pending approval")
        console.print("[yellow]📋 Request submitted for review.[/]\n")
        return

    new_balance = account["balance"] - amount
    db_manager.update_balance(acc_id, new_balance)
    db_manager.add_transaction(acc_id, "withdrawal", amount, f"Cash withdrawal by {session.username}")
    db_manager.add_audit_log("WITHDRAWAL", session.username, acc_id, f"₹{amount:,.2f} withdrawn")

    console.print(f"\n[bold green]✅ ₹{amount:,.2f} withdrawn successfully![/]")
    console.print(f"[green]   New Balance: ₹{new_balance:,.2f}[/]\n")


def customer_transfer(session: Session):
    """Transfer money to another account."""
    accounts = db_manager.get_accounts_by_user(session.user_id)
    if not accounts:
        console.print("[yellow]No accounts found.[/]")
        return

    customer_view_balance(session)

    src_id = IntPrompt.ask("[cyan]From Account #[/]")
    src_account = db_manager.get_account_by_id(src_id)

    if not src_account or src_account["user_id"] != session.user_id:
        console.print("[red]Invalid source account or access denied.[/]")
        return

    dst_id = IntPrompt.ask("[cyan]To Account #[/]")
    dst_account = db_manager.get_account_by_id(dst_id)

    if not dst_account:
        console.print("[red]Destination account not found.[/]")
        return

    if src_id == dst_id:
        console.print("[red]Cannot transfer to the same account.[/]")
        return

    amount = FloatPrompt.ask("[cyan]Transfer Amount (₹)[/]")
    if amount <= 0:
        console.print("[red]Amount must be positive.[/]")
        return

    if amount > src_account["balance"]:
        console.print("[red]Insufficient balance![/]")
        return

    # Large transfers require approval
    if amount >= LARGE_AMOUNT_THRESHOLD:
        console.print(f"[yellow]⚠ Transfers ≥ ₹{LARGE_AMOUNT_THRESHOLD:,.2f} require accountant approval.[/]")
        db_manager.create_request(src_id, "large_transfer", amount,
                                  f"Transfer to Acc #{dst_id} by {session.username}")
        db_manager.add_audit_log("TRANSFER_REQUEST", session.username, src_id,
                                 f"₹{amount:,.2f} to Acc #{dst_id} — pending")
        console.print("[yellow]📋 Request submitted for review.[/]\n")
        return

    # Execute transfer
    db_manager.update_balance(src_id, src_account["balance"] - amount)
    db_manager.update_balance(dst_id, dst_account["balance"] + amount)
    db_manager.add_transaction(src_id, "transfer", amount,
                               f"Transfer to Acc #{dst_id}", "completed", dst_id)
    db_manager.add_transaction(dst_id, "deposit", amount,
                               f"Transfer from Acc #{src_id}", "completed", src_id)
    db_manager.add_audit_log("TRANSFER", session.username, src_id,
                             f"₹{amount:,.2f} → Acc #{dst_id}")

    console.print(f"\n[bold green]✅ ₹{amount:,.2f} transferred to Acc #{dst_id}![/]")
    console.print(f"[green]   New Balance: ₹{src_account['balance'] - amount:,.2f}[/]\n")


def customer_statement(session: Session):
    """View transaction history."""
    accounts = db_manager.get_accounts_by_user(session.user_id)
    if not accounts:
        console.print("[yellow]No accounts found.[/]")
        return

    customer_view_balance(session)

    acc_id = IntPrompt.ask("[cyan]Enter Account #[/]")
    account = db_manager.get_account_by_id(acc_id)

    if not account or account["user_id"] != session.user_id:
        console.print("[red]Invalid account or access denied.[/]")
        return

    txns = db_manager.get_transactions_by_account(acc_id)

    if not txns:
        console.print("[yellow]No transactions found.[/]")
        return

    table = Table(title=f"📜 Statement — Account #{acc_id}", box=box.ROUNDED, show_lines=True)
    table.add_column("Txn #", style="cyan", justify="center")
    table.add_column("Type", style="magenta")
    table.add_column("Amount (₹)", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("Description")
    table.add_column("Status", justify="center")

    for txn in txns:
        color = "green" if txn["txn_type"] == "deposit" else "red"
        sign = "+" if txn["txn_type"] == "deposit" else "-"
        table.add_row(
            str(txn["txn_id"]),
            txn["txn_type"].upper(),
            f"[{color}]{sign}₹{txn['amount']:,.2f}[/]",
            txn["timestamp"],
            txn["description"],
            txn["status"].upper(),
        )

    console.print(table)
    console.print()


# ═══════════════════════════════════════════════
# ACCOUNTANT FEATURES
# ═══════════════════════════════════════════════

def accountant_view_requests(session: Session):
    """View all pending requests."""
    requests = db_manager.get_pending_requests()

    if not requests:
        console.print("[green]No pending requests! ✨[/]\n")
        return

    table = Table(title="📋 Pending Requests", box=box.ROUNDED, show_lines=True)
    table.add_column("Req #", style="cyan", justify="center")
    table.add_column("Acc #", justify="center")
    table.add_column("Type", style="magenta")
    table.add_column("Amount (₹)", justify="right")
    table.add_column("Details")
    table.add_column("Created", style="dim")

    for req in requests:
        table.add_row(
            str(req["request_id"]),
            str(req["account_id"]),
            req["request_type"].replace("_", " ").upper(),
            f"₹{req['amount']:,.2f}",
            req["details"],
            req["created_at"],
        )

    console.print(table)
    console.print()


def accountant_process_request(session: Session):
    """Approve or reject a pending request."""
    accountant_view_requests(session)

    requests = db_manager.get_pending_requests()
    if not requests:
        return

    req_id = IntPrompt.ask("[cyan]Enter Request # to process[/]")

    # Find the request
    target = None
    for r in requests:
        if r["request_id"] == req_id:
            target = r
            break

    if not target:
        console.print("[red]Request not found.[/]")
        return

    console.print(f"\n[bold]Request #{req_id}:[/]")
    console.print(f"   Type: {target['request_type']}")
    console.print(f"   Account: #{target['account_id']}")
    console.print(f"   Amount: ₹{target['amount']:,.2f}")
    console.print(f"   Details: {target['details']}\n")

    action = Prompt.ask("Action", choices=["approve", "reject", "cancel"])

    if action == "cancel":
        return

    if action == "approve":
        db_manager.update_request_status(req_id, "approved", session.username)

        # Execute the approved action
        account = db_manager.get_account_by_id(target["account_id"])
        if account:
            if target["request_type"] == "large_withdrawal":
                new_bal = account["balance"] - target["amount"]
                if new_bal >= 0:
                    db_manager.update_balance(target["account_id"], new_bal)
                    db_manager.add_transaction(
                        target["account_id"], "withdrawal", target["amount"],
                        f"Approved withdrawal (Req #{req_id})"
                    )
                    console.print(f"[green]✅ Withdrawal of ₹{target['amount']:,.2f} approved and executed.[/]")
                else:
                    console.print("[red]Insufficient balance — request approved but cannot execute.[/]")
            elif target["request_type"] == "large_transfer":
                # Parse target account from details
                new_bal = account["balance"] - target["amount"]
                if new_bal >= 0:
                    db_manager.update_balance(target["account_id"], new_bal)
                    db_manager.add_transaction(
                        target["account_id"], "transfer", target["amount"],
                        f"Approved transfer (Req #{req_id})"
                    )
                    console.print(f"[green]✅ Transfer of ₹{target['amount']:,.2f} approved and executed.[/]")
                else:
                    console.print("[red]Insufficient balance — request approved but cannot execute.[/]")
            elif target["request_type"] == "account_close":
                db_manager.close_account(target["account_id"])
                console.print(f"[green]✅ Account #{target['account_id']} closed.[/]")

        db_manager.add_audit_log("REQUEST_APPROVED", session.username, target["account_id"],
                                 f"Req #{req_id} ({target['request_type']}) approved")

    elif action == "reject":
        db_manager.update_request_status(req_id, "rejected", session.username)
        db_manager.add_audit_log("REQUEST_REJECTED", session.username, target["account_id"],
                                 f"Req #{req_id} ({target['request_type']}) rejected")
        console.print(f"[yellow]❌ Request #{req_id} rejected.[/]")

    console.print()


def accountant_view_all_accounts(session: Session):
    """View all customer accounts."""
    accounts = db_manager.get_all_accounts()

    if not accounts:
        console.print("[yellow]No accounts found.[/]")
        return

    table = Table(title="🏦 All Customer Accounts", box=box.ROUNDED, show_lines=True)
    table.add_column("Acc #", style="cyan", justify="center")
    table.add_column("Customer", style="bold")
    table.add_column("Email")
    table.add_column("Type", style="magenta")
    table.add_column("Balance (₹)", style="green", justify="right")
    table.add_column("Status", justify="center")

    for acc in accounts:
        status = "[green]Active[/]" if acc["is_active"] else "[red]Closed[/]"
        table.add_row(
            str(acc["account_id"]),
            acc["customer_name"],
            acc["email"],
            acc["account_type"].upper(),
            f"₹{acc['balance']:,.2f}",
            status,
        )

    console.print(table)
    console.print()


def accountant_create_account(session: Session):
    """Create a new customer account."""
    console.print(Rule("➕ Create New Account", style="yellow"))

    # Show existing users to help select
    users = db_manager.get_all_users()
    customers = [u for u in users if u["role"] == "customer"]

    if customers:
        table = Table(title="Existing Customers", box=box.SIMPLE)
        table.add_column("User ID", justify="center")
        table.add_column("Username")
        table.add_column("Full Name")
        for c in customers:
            table.add_row(str(c["user_id"]), c["username"], c["full_name"])
        console.print(table)
        console.print()

    user_id = IntPrompt.ask("[cyan]Customer User ID[/]")
    name = Prompt.ask("[cyan]Customer Full Name[/]")
    email = Prompt.ask("[cyan]Email[/]")
    phone = Prompt.ask("[cyan]Phone[/]")
    acc_type = Prompt.ask("[cyan]Account Type[/]", choices=["savings", "current", "fixed_deposit"], default="savings")
    balance = FloatPrompt.ask("[cyan]Initial Deposit (₹)[/]", default=0.0)

    acc_id = db_manager.create_account(name, email, phone, balance, acc_type, user_id)
    db_manager.add_audit_log("ACCOUNT_CREATED", session.username, acc_id,
                             f"{acc_type} account for {name}")

    console.print(f"\n[bold green]✅ Account #{acc_id} created successfully![/]\n")


def accountant_view_audit_log(session: Session):
    """View the audit log."""
    logs = db_manager.get_audit_logs()

    if not logs:
        console.print("[yellow]No audit log entries.[/]")
        return

    table = Table(title="📊 Audit Log", box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", justify="center")
    table.add_column("Action", style="cyan")
    table.add_column("By", style="yellow")
    table.add_column("Acc #", justify="center")
    table.add_column("Timestamp", style="dim")
    table.add_column("Details")

    for log in logs:
        table.add_row(
            str(log["log_id"]),
            log["action"],
            log["performed_by"],
            str(log["account_id"] or "—"),
            log["timestamp"],
            log["details"],
        )

    console.print(table)
    console.print()


def accountant_view_all_transactions(session: Session):
    """View all transactions."""
    txns = db_manager.get_all_transactions()

    if not txns:
        console.print("[yellow]No transactions found.[/]")
        return

    table = Table(title="📝 All Recent Transactions", box=box.ROUNDED, show_lines=True)
    table.add_column("Txn #", style="cyan", justify="center")
    table.add_column("Acc #", justify="center")
    table.add_column("Type", style="magenta")
    table.add_column("Amount (₹)", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("Description")
    table.add_column("Status", justify="center")

    for txn in txns:
        color = "green" if txn["txn_type"] == "deposit" else "red"
        sign = "+" if txn["txn_type"] == "deposit" else "-"
        table.add_row(
            str(txn["txn_id"]),
            str(txn["account_id"]),
            txn["txn_type"].upper(),
            f"[{color}]{sign}₹{txn['amount']:,.2f}[/]",
            txn["timestamp"],
            txn["description"],
            txn["status"].upper(),
        )

    console.print(table)
    console.print()


# ═══════════════════════════════════════════════
# MANAGER FEATURES
# ═══════════════════════════════════════════════

def manager_manage_users(session: Session):
    """User management submenu for manager."""
    while True:
        clear_screen()
        show_role_badge(session)
        console.print(Rule("👥 User Management", style="red"))

        users = db_manager.get_all_users()

        table = Table(title="All Users", box=box.ROUNDED, show_lines=True)
        table.add_column("ID", style="cyan", justify="center")
        table.add_column("Username", style="bold")
        table.add_column("Full Name")
        table.add_column("Role", style="magenta")
        table.add_column("Created", style="dim")
        table.add_column("Active", justify="center")

        for u in users:
            status = "[green]✓[/]" if u["is_active"] else "[red]✗[/]"
            table.add_row(
                str(u["user_id"]),
                u["username"],
                u["full_name"],
                u["role"].upper(),
                u["created_at"],
                status,
            )

        console.print(table)
        console.print()

        console.print("[1] Create New User")
        console.print("[2] Activate/Deactivate User")
        console.print("[3] Delete User")
        console.print("[0] Back")
        console.print()

        choice = Prompt.ask("Select", choices=["0", "1", "2", "3"])

        if choice == "0":
            break
        elif choice == "1":
            manager_create_user(session)
        elif choice == "2":
            manager_toggle_user(session)
        elif choice == "3":
            manager_delete_user(session)

        pause()


def manager_create_user(session: Session):
    """Create a new system user."""
    console.print(Rule("➕ Create New User", style="red"))

    username = Prompt.ask("[cyan]Username[/]")

    # Check if username exists
    if db_manager.get_user_by_username(username):
        console.print("[red]Username already exists![/]")
        return

    password = Prompt.ask("[cyan]Password[/]", password=True)
    full_name = Prompt.ask("[cyan]Full Name[/]")
    role = Prompt.ask("[cyan]Role[/]", choices=["customer", "accountant", "manager"])

    user_id = db_manager.create_user(username, auth.hash_password(password), role, full_name)
    db_manager.add_system_log("USER_CREATED", session.user_id, f"Created {role} user: {username}")
    db_manager.add_audit_log("USER_CREATED", session.username, details=f"New {role}: {username} (ID: {user_id})")

    console.print(f"\n[bold green]✅ User '{username}' (ID: {user_id}) created as {role.upper()}.[/]\n")


def manager_toggle_user(session: Session):
    """Activate or deactivate a user."""
    user_id = IntPrompt.ask("[cyan]User ID to toggle[/]")

    if user_id == session.user_id:
        console.print("[red]Cannot deactivate your own account![/]")
        return

    users = db_manager.get_all_users()
    target = None
    for u in users:
        if u["user_id"] == user_id:
            target = u
            break

    if not target:
        console.print("[red]User not found.[/]")
        return

    new_status = not target["is_active"]
    db_manager.toggle_user_active(user_id, new_status)

    status_text = "activated" if new_status else "deactivated"
    db_manager.add_system_log("USER_TOGGLED", session.user_id,
                              f"User {target['username']} {status_text}")

    console.print(f"[green]✅ User '{target['username']}' has been {status_text}.[/]\n")


def manager_delete_user(session: Session):
    """Delete a user permanently."""
    user_id = IntPrompt.ask("[cyan]User ID to delete[/]")

    if user_id == session.user_id:
        console.print("[red]Cannot delete your own account![/]")
        return

    users = db_manager.get_all_users()
    target = None
    for u in users:
        if u["user_id"] == user_id:
            target = u
            break

    if not target:
        console.print("[red]User not found.[/]")
        return

    if Confirm.ask(f"[red]Delete user '{target['username']}' permanently?[/]", default=False):
        db_manager.delete_user(user_id)
        db_manager.add_system_log("USER_DELETED", session.user_id,
                                  f"Deleted user: {target['username']}")
        console.print(f"[green]✅ User '{target['username']}' deleted.[/]\n")
    else:
        console.print("[yellow]Cancelled.[/]\n")


def manager_system_logs(session: Session):
    """View system logs."""
    logs = db_manager.get_system_logs()

    if not logs:
        console.print("[yellow]No system logs.[/]")
        return

    table = Table(title="🔍 System Logs", box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", justify="center")
    table.add_column("Action", style="red")
    table.add_column("User ID", justify="center")
    table.add_column("Timestamp", style="dim")
    table.add_column("Details")

    for log in logs:
        table.add_row(
            str(log["log_id"]),
            log["action"],
            str(log["user_id"]),
            log["timestamp"],
            log["details"],
        )

    console.print(table)
    console.print()


def manager_generate_report(session: Session):
    """Generate a summary report."""
    console.print(Rule("📈 Bank Summary Report", style="red"))

    total_balance = db_manager.get_total_balance()
    total_deposits = db_manager.get_total_deposits()
    total_withdrawals = db_manager.get_total_withdrawals()
    account_count = db_manager.get_account_count()
    user_count = db_manager.get_user_count()
    pending = db_manager.get_pending_requests()

    # Summary panel
    summary = Table(box=box.ROUNDED, show_header=False, show_lines=True, pad_edge=True)
    summary.add_column("Metric", style="bold cyan", min_width=25)
    summary.add_column("Value", style="bold green", justify="right", min_width=20)

    summary.add_row("Total Balance (All Accounts)", f"₹{total_balance:,.2f}")
    summary.add_row("Total Deposits", f"₹{total_deposits:,.2f}")
    summary.add_row("Total Withdrawals", f"₹{total_withdrawals:,.2f}")
    summary.add_row("Active Accounts", str(account_count))
    summary.add_row("Active Users", str(user_count))
    summary.add_row("Pending Requests", str(len(pending)))

    console.print(Panel(summary, title="[bold]Bank Overview[/]", border_style="red"))

    # Branches
    branches = db_manager.get_branch_info()
    if branches:
        branch_table = Table(title="🏛 Branches", box=box.ROUNDED)
        branch_table.add_column("ID", justify="center")
        branch_table.add_column("Name", style="bold")
        branch_table.add_column("Location")
        branch_table.add_column("Manager ID", justify="center")

        for b in branches:
            branch_table.add_row(
                str(b["branch_id"]),
                b["branch_name"],
                b["location"],
                str(b["manager_id"] or "—"),
            )
        console.print(branch_table)

    db_manager.add_system_log("REPORT_GENERATED", session.user_id, "Bank summary report generated")
    console.print()


# ═══════════════════════════════════════════════
# DASHBOARD MENUS
# ═══════════════════════════════════════════════

def customer_dashboard(session: Session):
    """Main menu for customer role."""
    while True:
        clear_screen()
        show_role_badge(session)
        console.print(Rule("🏠 Customer Dashboard", style="green"))
        console.print()

        console.print("[1] 💰 View Balance")
        console.print("[2] 💵 Deposit")
        console.print("[3] 🏧 Withdraw")
        console.print("[4] 🔄 Transfer")
        console.print("[5] 📜 Account Statement")
        console.print("[0] 🚪 Logout")
        console.print()

        choice = Prompt.ask("Select", choices=["0", "1", "2", "3", "4", "5"])

        if choice == "0":
            session.logout()
            console.print("[yellow]Logged out. Goodbye! 👋[/]")
            pause()
            return
        elif choice == "1":
            customer_view_balance(session)
        elif choice == "2":
            customer_deposit(session)
        elif choice == "3":
            customer_withdraw(session)
        elif choice == "4":
            customer_transfer(session)
        elif choice == "5":
            customer_statement(session)

        pause()


def accountant_dashboard(session: Session):
    """Main menu for accountant role."""
    while True:
        clear_screen()
        show_role_badge(session)
        console.print(Rule("🏠 Accountant Dashboard", style="yellow"))
        console.print()

        console.print("[1] 📋 View Pending Requests")
        console.print("[2] ✅ Process Request (Approve/Reject)")
        console.print("[3] 🏦 View All Accounts")
        console.print("[4] ➕ Create New Account")
        console.print("[5] 📝 View All Transactions")
        console.print("[6] 📊 View Audit Log")
        console.print("[0] 🚪 Logout")
        console.print()

        choice = Prompt.ask("Select", choices=["0", "1", "2", "3", "4", "5", "6"])

        if choice == "0":
            session.logout()
            console.print("[yellow]Logged out. Goodbye! 👋[/]")
            pause()
            return
        elif choice == "1":
            accountant_view_requests(session)
        elif choice == "2":
            accountant_process_request(session)
        elif choice == "3":
            accountant_view_all_accounts(session)
        elif choice == "4":
            accountant_create_account(session)
        elif choice == "5":
            accountant_view_all_transactions(session)
        elif choice == "6":
            accountant_view_audit_log(session)

        pause()


def manager_dashboard(session: Session):
    """Main menu for manager role."""
    while True:
        clear_screen()
        show_role_badge(session)
        console.print(Rule("🏠 Manager Dashboard", style="red"))
        console.print()

        console.print("[1] 📈 Generate Report")
        console.print("[2] 👥 Manage Users")
        console.print("[3] 🔍 View System Logs")
        console.print("[4] 📊 View Audit Log")
        console.print("[5] 📋 View Pending Requests")
        console.print("[6] ✅ Process Request")
        console.print("[7] 🏦 View All Accounts")
        console.print("[8] 📝 View All Transactions")
        console.print("[9] ➕ Create Account")
        console.print("[0] 🚪 Logout")
        console.print()

        choice = Prompt.ask("Select", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])

        if choice == "0":
            session.logout()
            console.print("[yellow]Logged out. Goodbye! 👋[/]")
            pause()
            return
        elif choice == "1":
            manager_generate_report(session)
        elif choice == "2":
            manager_manage_users(session)
        elif choice == "3":
            manager_system_logs(session)
        elif choice == "4":
            accountant_view_audit_log(session)
        elif choice == "5":
            accountant_view_requests(session)
        elif choice == "6":
            accountant_process_request(session)
        elif choice == "7":
            accountant_view_all_accounts(session)
        elif choice == "8":
            accountant_view_all_transactions(session)
        elif choice == "9":
            accountant_create_account(session)

        pause()


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    """Application entry point."""
    # Initialize databases
    db_manager.init_all_databases()

    while True:
        # Login
        session = login_screen()

        # Route to role-specific dashboard
        if session.role == "customer":
            customer_dashboard(session)
        elif session.role == "accountant":
            accountant_dashboard(session)
        elif session.role == "manager":
            manager_dashboard(session)
        else:
            console.print(f"[red]Unknown role: {session.role}[/]")
            session.logout()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Session terminated. Goodbye! 👋[/]")
        sys.exit(0)

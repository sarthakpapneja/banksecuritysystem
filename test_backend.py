import db_manager
import auth

print("Testing Backend Features")

# 1. Login Authentication
print("\n--- Testing Login ---")
user = db_manager.get_user_by_username("john_doe")
print(f"User retrieved: {user['username']}")

# 2. QR Code functionality (Generate QR code string)
print("\n--- Testing QR Code ---")
acc = db_manager.get_accounts_by_user(user['user_id'])[0]
qr_data = f"upi://pay?pa={acc['account_id']}@apex&pn={user['full_name']}"
print(f"QR Data generated: {qr_data}")

# 3. Requesting a Loan
print("\n--- Testing Loan Application ---")
# Simulate adding a loan request
loan_amount = 5000.00
try:
    req_id = db_manager.create_request(acc["account_id"], "loan", loan_amount, "Home improvement loan")
    print(f"Loan request created successfully. Request ID: {req_id}")
    
    # Clean up right after
    conn = db_manager.get_connection("accountants")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pending_requests WHERE request_id = ?", (req_id,))
    conn.commit()
    conn.close()
    print("Test loan request cleaned up.")
except Exception as e:
    print(f"Failed to create loan request: {e}")

# 4. Two Step Verification Status
print("\n--- Testing 2FA Configuration ---")
if 'two_factor_enabled' in user:
    print(f"2FA Enabled: {user['two_factor_enabled']}")
else:
    print("2FA status column not explicitly returned in get_user_by_username, but table might have it.")

print("\nBackend testing completed.")

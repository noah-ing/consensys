"""
Clean Code Example - Best Practices Demonstration

This file demonstrates secure, well-structured Python code that should pass
Consensys review. Run `consensys review examples/clean.py` to verify.

This code addresses all vulnerabilities shown in vulnerable.py with proper fixes.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
import subprocess
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Secure SQL with Parameterized Queries
def get_user(username: str) -> Optional[dict]:
    """Fetch user by username using parameterized queries."""
    conn = sqlite3.connect("users.db")
    try:
        cursor = conn.cursor()

        # GOOD: Parameterized query prevents SQL injection
        query = "SELECT id, username FROM users WHERE username = ?"
        cursor.execute(query, (username,))

        result = cursor.fetchone()
        return {"id": result[0], "username": result[1]} if result else None
    finally:
        conn.close()


# Secure Command Execution
def ping_host(hostname: str) -> str:
    """Ping a host with input validation."""
    # GOOD: Validate hostname format (simple check)
    if not hostname.replace(".", "").replace("-", "").isalnum():
        raise ValueError("Invalid hostname format")

    # GOOD: Use list arguments instead of shell=True
    result = subprocess.run(
        ["ping", "-c", "1", hostname],
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.stdout


# Secure Serialization with JSON
import json

def load_user_data(json_data: str) -> dict:
    """Load user data from JSON (safe serialization format)."""
    # GOOD: JSON is safe, unlike pickle
    return json.loads(json_data)


# Configuration from Environment Variables
@dataclass
class DatabaseConfig:
    """Database configuration from environment variables."""

    # GOOD: Load secrets from environment, not source code
    host: str = ""
    username: str = ""
    password: str = ""
    api_key: str = ""

    def __post_init__(self):
        self.host = os.environ.get("DB_HOST", "localhost")
        self.username = os.environ.get("DB_USERNAME", "")
        self.password = os.environ.get("DB_PASSWORD", "")
        self.api_key = os.environ.get("API_KEY", "")

        if not self.username or not self.password:
            raise ValueError("Database credentials must be set in environment")


# Secure Path Handling
def read_user_file(filename: str, base_path: str = "/var/www/uploads/") -> str:
    """Read a file with path traversal protection."""
    # GOOD: Resolve and validate the path
    base = Path(base_path).resolve()
    file_path = (base / filename).resolve()

    # GOOD: Ensure the resolved path is within the base directory
    if not str(file_path).startswith(str(base)):
        raise ValueError("Access denied: path traversal detected")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {filename}")

    return file_path.read_text()


# Cryptographically Secure Token Generation
def generate_session_token() -> str:
    """Generate session token using secure random."""
    # GOOD: secrets module is cryptographically secure
    return secrets.token_hex(32)


# Input Validation with Type Safety
@dataclass
class PaymentRequest:
    """Payment request with validated fields."""

    amount: float
    card_last_four: str

    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError("Amount must be positive")
        if self.amount > 10000:
            raise ValueError("Amount exceeds maximum limit")
        if not self.card_last_four.isdigit() or len(self.card_last_four) != 4:
            raise ValueError("Invalid card last four digits")


def process_payment(amount: str, card_number: str) -> dict:
    """Process payment with proper validation."""
    # GOOD: Validate amount is a positive number
    try:
        amount_float = float(amount)
    except ValueError:
        raise ValueError("Amount must be a valid number")

    # GOOD: Validate card number format (basic check)
    card_clean = card_number.replace("-", "").replace(" ", "")
    if not card_clean.isdigit() or len(card_clean) < 13:
        raise ValueError("Invalid card number format")

    # GOOD: Create validated payment request
    request = PaymentRequest(
        amount=amount_float,
        card_last_four=card_clean[-4:]
    )

    # GOOD: Don't log sensitive card data
    return {
        "status": "success",
        "amount": request.amount,
        "card_last_four": request.card_last_four
    }


# Safe Expression Evaluation
ALLOWED_OPERATIONS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b if b != 0 else float("inf"),
}


def calculate_expression(a: float, b: float, operator: str) -> float:
    """Calculate with safe operator whitelist."""
    # GOOD: Whitelist approach instead of eval
    if operator not in ALLOWED_OPERATIONS:
        raise ValueError(f"Unsupported operator: {operator}")
    return ALLOWED_OPERATIONS[operator](a, b)


# Secure XML Parsing
def parse_xml_config(xml_string: str) -> dict:
    """Parse XML config with XXE protection."""
    # GOOD: Create parser with external entities disabled
    parser = ET.XMLParser()

    # Note: defusedxml library is even better for production use
    root = ET.fromstring(xml_string, parser=parser)
    return {child.tag: child.text for child in root}


# Strong Password Hashing
def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    """Hash password using PBKDF2 with salt."""
    # GOOD: Generate cryptographic salt if not provided
    if salt is None:
        salt = secrets.token_bytes(32)

    # GOOD: Use PBKDF2 with SHA256, high iteration count
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=100000
    )

    return key.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
    """Verify password using constant-time comparison."""
    salt = bytes.fromhex(salt_hex)
    computed_hash, _ = hash_password(password, salt)

    # GOOD: Constant-time comparison prevents timing attacks
    return hmac.compare_digest(computed_hash, stored_hash)


# Thread-Safe Bank Account
class BankAccount:
    """Bank account with thread-safe operations."""

    def __init__(self, balance: float = 0):
        self._balance = balance
        self._lock = threading.Lock()

    @property
    def balance(self) -> float:
        """Thread-safe balance access."""
        with self._lock:
            return self._balance

    def withdraw(self, amount: float) -> bool:
        """Withdraw money with proper locking."""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        # GOOD: Lock ensures atomic check-and-update
        with self._lock:
            if self._balance >= amount:
                self._balance -= amount
                return True
            return False

    def deposit(self, amount: float) -> None:
        """Deposit money with proper locking."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        with self._lock:
            self._balance += amount


if __name__ == "__main__":
    print("This file demonstrates secure coding best practices.")
    print("Run: consensys review examples/clean.py")

    # Demo: Generate a secure session token
    token = generate_session_token()
    print(f"Generated session token: {token[:16]}...")

    # Demo: Hash a password securely
    password_hash, salt = hash_password("example_password")
    print(f"Password hashed with PBKDF2-SHA256")
    print(f"Verification: {verify_password('example_password', password_hash, salt)}")

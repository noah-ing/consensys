"""
Vulnerable Code Example - For Educational Purposes Only

This file contains common security vulnerabilities that Consensys will detect.
Run `consensys review examples/vulnerable.py` to see the AI agents identify issues.

WARNING: Do not use this code in production!
"""

import os
import pickle
import sqlite3
import subprocess
from typing import Any


# SQL Injection Vulnerability
def get_user(username: str) -> dict:
    """Fetch user by username - VULNERABLE to SQL injection."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # BAD: Direct string interpolation in SQL query
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)

    result = cursor.fetchone()
    conn.close()
    return {"id": result[0], "username": result[1]} if result else None


# Command Injection Vulnerability
def ping_host(hostname: str) -> str:
    """Ping a host - VULNERABLE to command injection."""
    # BAD: User input passed directly to shell command
    result = subprocess.run(
        f"ping -c 1 {hostname}",
        shell=True,
        capture_output=True,
        text=True
    )
    return result.stdout


# Insecure Deserialization
def load_user_data(serialized_data: bytes) -> Any:
    """Load user data - VULNERABLE to arbitrary code execution."""
    # BAD: pickle.loads on untrusted data allows code execution
    return pickle.loads(serialized_data)


# Hardcoded Secrets
class DatabaseConfig:
    """Database configuration - VULNERABLE: hardcoded credentials."""

    # BAD: Hardcoded credentials in source code
    HOST = "db.example.com"
    USERNAME = "admin"
    PASSWORD = "super_secret_password_123"
    API_KEY = "sk-1234567890abcdef"


# Path Traversal Vulnerability
def read_user_file(filename: str) -> str:
    """Read a file from user directory - VULNERABLE to path traversal."""
    base_path = "/var/www/uploads/"

    # BAD: No validation on filename, allows ../../../etc/passwd
    file_path = base_path + filename

    with open(file_path, "r") as f:
        return f.read()


# Insecure Random Number Generation
import random

def generate_session_token() -> str:
    """Generate session token - VULNERABLE: weak randomness."""
    # BAD: random module is not cryptographically secure
    return "".join(random.choice("abcdef0123456789") for _ in range(32))


# Missing Input Validation
def process_payment(amount: str, card_number: str) -> dict:
    """Process payment - VULNERABLE: no input validation."""
    # BAD: No validation on amount (could be negative)
    # BAD: No validation on card number format
    # BAD: Card number logged in plaintext
    print(f"Processing payment of ${amount} for card {card_number}")

    return {
        "status": "success",
        "amount": float(amount),  # Could raise ValueError
        "card_last_four": card_number[-4:]
    }


# Eval Injection
def calculate_expression(expression: str) -> Any:
    """Calculate math expression - VULNERABLE to code execution."""
    # BAD: eval() on user input allows arbitrary code execution
    return eval(expression)


# XML External Entity (XXE) Vulnerability
import xml.etree.ElementTree as ET

def parse_xml_config(xml_string: str) -> dict:
    """Parse XML config - VULNERABLE to XXE attacks."""
    # BAD: Default XML parser doesn't disable external entities
    root = ET.fromstring(xml_string)
    return {child.tag: child.text for child in root}


# Weak Cryptography
import hashlib

def hash_password(password: str) -> str:
    """Hash password - VULNERABLE: weak hashing algorithm."""
    # BAD: MD5 is cryptographically broken, no salt used
    return hashlib.md5(password.encode()).hexdigest()


# Race Condition Vulnerability
class BankAccount:
    """Bank account - VULNERABLE to race conditions."""

    def __init__(self, balance: float = 0):
        self.balance = balance

    def withdraw(self, amount: float) -> bool:
        """Withdraw money - VULNERABLE: no locking mechanism."""
        # BAD: Time-of-check to time-of-use (TOCTOU) race condition
        if self.balance >= amount:
            # Attacker could modify balance between check and update
            self.balance -= amount
            return True
        return False


if __name__ == "__main__":
    # Demo usage (don't actually run these with untrusted input!)
    print("This file demonstrates common security vulnerabilities.")
    print("Run: consensys review examples/vulnerable.py")

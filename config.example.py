"""
Configuration template for the Smart Pharmacy Management System.

HOW TO USE:
  1. Copy this file and rename the copy to  config.py
  2. Put your own MySQL password below
  3. config.py is git-ignored, so your password is never uploaded to GitHub
"""

# ---- MySQL connection settings ----
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "YOUR_MYSQL_PASSWORD_HERE",   # <-- put your MySQL root password here
    "database": "pharmacy_db",
}

# ---- Flask settings ----
SECRET_KEY = "change-me-to-any-random-string"

# ---- Business settings ----
DEFAULT_TAX_PERCENT = 10.0   # tax applied at checkout

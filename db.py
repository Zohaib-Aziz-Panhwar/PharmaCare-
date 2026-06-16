"""
Small database helper module.

Keeps all the MySQL connection code in one place so the routes in
app.py stay short and easy to read.
"""

import mysql.connector
from config import DB_CONFIG


def get_connection():
    """Open and return a new MySQL connection."""
    return mysql.connector.connect(**DB_CONFIG)


def query(sql, params=None, fetchone=False):
    """
    Run a SELECT and return the rows as a list of dictionaries
    (or a single dict if fetchone=True).
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    result = cur.fetchone() if fetchone else cur.fetchall()
    cur.close()
    conn.close()
    return result


def execute(sql, params=None):
    """
    Run an INSERT / UPDATE / DELETE and commit.
    Returns the new row's id (lastrowid) when useful.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    new_id = cur.lastrowid
    cur.close()
    conn.close()
    return new_id


def log_activity(user_id, action):
    """Write a row to the audit trail (activity_log)."""
    try:
        execute(
            "INSERT INTO activity_log (user_id, action) VALUES (%s, %s)",
            (user_id, action),
        )
    except Exception:
        # Logging should never crash the main action.
        pass

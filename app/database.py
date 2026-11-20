import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "nms.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_ip TEXT NOT NULL,
                check_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                latency_ms REAL,
                checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS device_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_ip TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
        """)
                # -------- ALERT MANAGEMENT UPGRADE --------

        columns = [
            column[1]
            for column in connection.execute(
                "PRAGMA table_info(device_alerts)"
            ).fetchall()
        ]

        if "severity" not in columns:
            connection.execute("""
                ALTER TABLE device_alerts
                ADD COLUMN severity TEXT NOT NULL DEFAULT 'WARNING'
            """)

        if "acknowledged" not in columns:
            connection.execute("""
                ALTER TABLE device_alerts
                ADD COLUMN acknowledged INTEGER NOT NULL DEFAULT 0
            """)

        if "acknowledged_at" not in columns:
            connection.execute("""
                ALTER TABLE device_alerts
                ADD COLUMN acknowledged_at TEXT
            """)


def save_result(
    device_ip,
    check_type,
    status,
    details=None,
    latency_ms=None,
):
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO monitoring_results (
                device_ip, check_type, status, details, latency_ms
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            device_ip,
            check_type,
            status,
            details,
            latency_ms,
        ))


def get_recent_results(limit=20):
    limit = max(1, min(int(limit), 500))

    with get_connection() as connection:
        return connection.execute("""
            SELECT *
            FROM monitoring_results
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
def resolve_device_alert(device_ip, alert_type):
    with get_connection() as connection:
        connection.execute("""
            UPDATE device_alerts
            SET status = 'RESOLVED',
                resolved_at = CURRENT_TIMESTAMP
            WHERE device_ip = ?
              AND alert_type = ?
              AND status = 'ACTIVE'
        """, (device_ip, alert_type)) 
# -------- ACKNOWLEDGE DEVICE ALERT --------

def acknowledge_device_alert(alert_id):
    with get_connection() as connection:
        connection.execute("""
            UPDATE device_alerts
            SET acknowledged = 1,
                acknowledged_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND status = 'ACTIVE'
        """, (alert_id,))        
def get_device_alerts(limit=100):
    limit = max(1, min(int(limit), 500))

    with get_connection() as connection:
        return connection.execute("""
            SELECT *
            FROM device_alerts
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()        


def create_device_alert(device_ip, alert_type, message):
    with get_connection() as connection:

        # Determine alert severity
        if alert_type == "DEVICE_UNREACHABLE":
            severity = "CRITICAL"
        elif "LATENCY" in alert_type:
            severity = "WARNING"
        else:
            severity = "INFO"

        # Prevent duplicate active alerts
        existing_alert = connection.execute("""
            SELECT id
            FROM device_alerts
            WHERE device_ip = ?
              AND alert_type = ?
              AND status = 'ACTIVE'
        """, (device_ip, alert_type)).fetchone()

        if existing_alert:
            return False

        # Insert new alert
        connection.execute("""
            INSERT INTO device_alerts (
                device_ip,
                alert_type,
                message,
                status,
                severity
            )
            VALUES (?, ?, ?, 'ACTIVE', ?)
        """, (device_ip, alert_type, message, severity))

        return True
        
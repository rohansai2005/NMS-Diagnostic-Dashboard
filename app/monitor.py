import time
import subprocess
import re
import sqlite3

from app.database import (
    save_result,
    create_device_alert,
    resolve_device_alert
)

from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "nms.db"

MONITOR_INTERVAL = 60


def check_device(device_ip):
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "1000", device_ip],
            capture_output=True,
            text=True,
            timeout=3
        )

        if result.returncode == 0:
            match = re.search(
                r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
                result.stdout,
                re.IGNORECASE
            )

            latency = float(match.group(1)) if match else None
            return "ONLINE", latency

        return "OFFLINE", None

    except subprocess.TimeoutExpired:
        return "OFFLINE", None


def get_monitored_devices():
    connection = sqlite3.connect(DATABASE_PATH)

    query = """
        SELECT DISTINCT device_ip
        FROM monitoring_results
        WHERE check_type IN ('DISCOVERY', 'REACHABILITY')
    """

    devices = connection.execute(query).fetchall()
    connection.close()

    return [device[0] for device in devices]


def run_monitoring_cycle():
    devices = get_monitored_devices()

    if not devices:
        print("No discovered devices available.")
        return

    for device_ip in devices:
        status, latency = check_device(device_ip)

        save_result(
            device_ip,
            "REACHABILITY",
            status,
            "Automatic monitoring",
            latency
        )

        if status == "OFFLINE":
            create_device_alert(
                device_ip,
                "DEVICE_UNREACHABLE",
                f"Device {device_ip} is unreachable."
            )
            print(f"[OFFLINE] {device_ip}")

        else:
            resolve_device_alert(
                device_ip,
                "DEVICE_UNREACHABLE"
            )
            print(f"[ONLINE] {device_ip} | Latency: {latency} ms")


def start_monitoring():
    print("NMS Automatic Monitoring Started")

    while True:
        try:
            run_monitoring_cycle()
        except Exception as error:
            print(f"Monitoring error: {error}")

        print("Next health check in 60 seconds...")
        time.sleep(MONITOR_INTERVAL)


if __name__ == "__main__":
    start_monitoring()
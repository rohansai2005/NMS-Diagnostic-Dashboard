import json
import re
import sqlite3
import subprocess
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from app.database import (
    acknowledge_device_alert,
    create_device_alert,
    resolve_device_alert,
    save_result,
    initialize_database,
)
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    
    page_title="NMS Network Monitoring",
    page_icon="🌐",
    layout="wide",
)
initialize_database()

DATABASE_PATH = Path(__file__).resolve().parent / "app" / "nms.db"


# ============================================================
# DATABASE AND NETWORK FUNCTIONS
# ============================================================

def load_data():
    with sqlite3.connect(DATABASE_PATH) as connection:
        return pd.read_sql_query(
            "SELECT * FROM monitoring_results ORDER BY id DESC",
            connection,
        )


def load_alerts():
    with sqlite3.connect(DATABASE_PATH) as connection:
        return pd.read_sql_query(
            "SELECT * FROM device_alerts ORDER BY id DESC",
            connection,
        )


def load_topology():
    with sqlite3.connect(DATABASE_PATH) as connection:
        return pd.read_sql_query(
            """
            SELECT device_ip, details, checked_at
            FROM monitoring_results
            WHERE check_type = 'TOPOLOGY'
              AND status = 'SUCCESS'
            ORDER BY id DESC
            """,
            connection,
        )


def check_device_reachability(device_ip):
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "1000", str(device_ip)],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            match = re.search(
                r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
                result.stdout,
                re.IGNORECASE,
            )
            latency = float(match.group(1)) if match else None
            return "ONLINE", latency
        return "OFFLINE", None
    except (subprocess.TimeoutExpired, OSError):
        return "OFFLINE", None


def run_health_checks(dataframe):
    devices = dataframe.loc[
        dataframe["check_type"].isin(["DISCOVERY", "REACHABILITY"]),
        "device_ip",
    ].dropna().unique()

    if len(devices) == 0:
        st.warning("No discovered devices are available for health checks.")
        return

    for device_ip in devices:
        status, latency = check_device_reachability(device_ip)
        save_result(
            device_ip,
            "REACHABILITY",
            status,
            "Manual dashboard health check",
            latency,
        )

        if status == "OFFLINE":
            create_device_alert(
                device_ip,
                "DEVICE_UNREACHABLE",
                f"Device {device_ip} is unreachable.",
            )
        else:
            resolve_device_alert(device_ip, "DEVICE_UNREACHABLE")

    st.success("Device health checks completed successfully!")


# ============================================================
# PRESENTATION
# ============================================================

st.markdown(
    """
    <style>
    /* Elegant enterprise typography: Manrope for headings, Inter for UI/body.
       System-font fallbacks keep the dashboard readable if Google Fonts are unavailable. */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');

    :root {
        --nms-bg: #0b1220;
        --nms-panel: #142238;
        --nms-panel-2: #1b2b43;
        --nms-border: #2b405c;
        --nms-cyan: #38bdf8;
        --nms-muted: #9aabc2;
        --nms-text: #e8eef7;
    }
    .stApp {
        background:
            radial-gradient(circle at 85% 0%, rgba(14,116,144,.13), transparent 30%),
            var(--nms-bg);
        color: var(--nms-text);
    }
    html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', 'Aptos', 'Segoe UI', sans-serif !important;
        font-feature-settings: "cv11", "ss01";
        letter-spacing: .005em;
    }
    h1, h2, h3, h4, .nms-title, [data-testid="stMetricValue"] {
        font-family: 'Manrope', 'Inter', 'Aptos', 'Segoe UI', sans-serif !important;
        letter-spacing: -.025em;
    }
    h1 { font-weight: 800 !important; }
    h2 { font-weight: 750 !important; }
    h3 { font-weight: 700 !important; }
    p, label, button, input, textarea, [data-testid="stCaptionContainer"] {
        font-family: 'Inter', 'Aptos', 'Segoe UI', sans-serif !important;
    }
    .block-container { padding-top: 1.35rem; padding-bottom: 2.5rem; max-width: 1500px; }
    h1 { color: var(--nms-text) !important; font-weight: 800 !important; letter-spacing: -.7px; }
    h2 { color: var(--nms-text) !important; font-weight: 750 !important; letter-spacing: -.35px; }
    h3 { color: #dbeafe !important; font-weight: 700 !important; }
    p, label, [data-testid="stCaptionContainer"] { color: var(--nms-muted); }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #172941, #101c2e);
        padding: 18px 19px;
        border-radius: 15px;
        border: 1px solid var(--nms-border);
        box-shadow: 0 8px 22px rgba(0,0,0,.15);
        min-height: 112px;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Inter', 'Aptos', 'Segoe UI', sans-serif !important;
        color: #b8c8da !important;
        font-size: .84rem !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.25 !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--nms-cyan) !important;
        font-size: clamp(1.25rem, 1.65vw, 1.7rem) !important;
        font-weight: 800 !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
        line-height: 1.2 !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-size: .78rem !important;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--nms-border);
        border-radius: 12px;
        overflow: hidden;
    }
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 9px;
        border: 1px solid #3b5878;
        font-weight: 650;
        min-height: 42px;
        transition: all .15s ease-in-out;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        border-color: var(--nms-cyan);
        color: var(--nms-cyan);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111d30 0%, #0d1727 100%);
        border-right: 1px solid var(--nms-border);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding: 5px 0; font-weight: 600; }
    [data-testid="stSelectbox"], [data-testid="stTextInput"], [data-testid="stDateInput"] {
        border-radius: 9px;
    }
    hr { border-color: var(--nms-border); margin: 1.25rem 0; }
    .nms-topbar {
        background: linear-gradient(115deg, #14263d 0%, #12364d 55%, #0e263b 100%);
        border: 1px solid #2b526e;
        border-radius: 17px;
        padding: 22px 25px;
        margin: 0 0 18px 0;
        box-shadow: 0 12px 30px rgba(0,0,0,.18);
    }
    .nms-eyebrow { color: #7dd3fc; text-transform: uppercase; letter-spacing: 2px; font-size: .72rem; font-weight: 800; }
    .nms-title { color: #f1f5f9; font-family: 'Manrope', 'Inter', sans-serif; font-size: 1.95rem; font-weight: 800; letter-spacing: -.035em; margin: 5px 0 2px 0; }
    .nms-subtitle { color: #b8c8da; font-size: .93rem; margin: 0; }
    .nms-section-note { color: #9aabc2; margin-top: -8px; margin-bottom: 15px; }
    .nms-footer {
        margin-top: 32px;
        padding: 15px 4px 4px 4px;
        border-top: 1px solid var(--nms-border);
        color: #8295ad;
        font-size: .8rem;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    """
    <h2 style="color:#38bdf8;">🌐 NMS CONTROL CENTER</h2>
    <p style="color:#94a3b8;">Network Monitoring System</p>
    """,
    unsafe_allow_html=True,
)
st.sidebar.divider()

selected_page = st.sidebar.radio(
    "MAIN MENU",
    [
        "Overview",
        "Device Monitoring",
        "Alerts Center",
        "Performance Analytics",
        "Network Topology",
        "Service & SNMP",
        "Reports",
    ],
)

st.sidebar.divider()
st.sidebar.caption("NMS Network Operations Center")

st.markdown(
    """
    <div class="nms-topbar">
        <div class="nms-eyebrow">Network Management System • Live Operations</div>
        <div class="nms-title">🌐 NMS Network Operations Center</div>
        <p class="nms-subtitle">
            Unified visibility for device health, network performance, alerts,
            topology, services and reporting.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

refresh_col, _ = st.columns([1, 5])
with refresh_col:
    if st.button("🔄 Refresh Dashboard"):
        st.rerun()

st.caption(f"CURRENT WORKSPACE  /  {selected_page.upper()}  /  Manual refresh enabled")


# ============================================================
# LOAD DATA AND COMMON CALCULATIONS
# ============================================================

try:
    df = load_data()
    alerts_df = load_alerts()
except Exception as error:
    st.error(f"Database error: {error}")
    st.info(
        "Check that app/nms.db exists and that the database tables "
        "monitoring_results and device_alerts have been created."
    )
    st.stop()

if df.empty:
    st.warning("No monitoring records found. Run your NMS modules first.")
    st.stop()

required_columns = {
    "id", "device_ip", "check_type", "status", "details",
    "checked_at", "latency_ms",
}
missing_columns = required_columns.difference(df.columns)
if missing_columns:
    st.error(f"Monitoring table is missing columns: {', '.join(sorted(missing_columns))}")
    st.stop()

if alerts_df.empty:
    # Keep an empty frame with expected columns so the page can render.
    alerts_df = pd.DataFrame(
        columns=[
            "id", "device_ip", "alert_type", "severity", "message",
            "status", "acknowledged", "created_at", "resolved_at",
        ]
    )

total_records = len(df)
unique_devices = df["device_ip"].nunique()
online_records = int((df["status"] == "ONLINE").sum())
offline_records = int((df["status"] == "OFFLINE").sum())
open_ports = int(
    (
        (df["check_type"] == "SERVICE_ENUMERATION")
        & (df["status"] == "OPEN")
    ).sum()
)

reachability_data = df[df["check_type"] == "REACHABILITY"].copy()
latency_data = reachability_data[
    (reachability_data["status"] == "ONLINE")
    & reachability_data["latency_ms"].notna()
]
average_latency = (
    round(float(latency_data["latency_ms"].mean()), 2)
    if not latency_data.empty
    else 0
)

total_ping_checks = len(reachability_data)
failed_ping_checks = int((reachability_data["status"] == "OFFLINE").sum())
packet_loss = (
    round((failed_ping_checks / total_ping_checks) * 100, 2)
    if total_ping_checks
    else 0
)

device_availability = (
    reachability_data.groupby("device_ip")
    .agg(
        total_checks=("status", "count"),
        successful_checks=("status", lambda values: (values == "ONLINE").sum()),
    )
    .reset_index()
)
if not device_availability.empty:
    device_availability["Availability (%)"] = (
        device_availability["successful_checks"]
        / device_availability["total_checks"]
        * 100
    ).round(2)

total_alerts = len(alerts_df)
active_alert_count = (
    int((alerts_df["status"] == "ACTIVE").sum())
    if "status" in alerts_df.columns else 0
)
resolved_alert_count = (
    int((alerts_df["status"] == "RESOLVED").sum())
    if "status" in alerts_df.columns else 0
)


# ============================================================
# PAGE 1: OVERVIEW
# ============================================================

if selected_page == "Overview":
    st.header("📊 Network Overview")
    st.caption("A consolidated view of network health, monitoring activity, and alerts.")

    metric_cols = st.columns(6)
    metric_cols[0].metric("Total Records", f"{total_records:,}")
    metric_cols[1].metric("Unique Devices", unique_devices)
    metric_cols[2].metric("Online Records", online_records)
    metric_cols[3].metric("Open Ports", open_ports)
    metric_cols[4].metric("Average Latency", f"{average_latency} ms")
    metric_cols[5].metric("Ping Failure Rate", f"{packet_loss}%")

    st.subheader("🚨 Alert Summary")
    alert_cols = st.columns(3)
    alert_cols[0].metric("Total Alerts", total_alerts)
    alert_cols[1].metric("Active Alerts", active_alert_count)
    alert_cols[2].metric("Resolved Alerts", resolved_alert_count)

    st.divider()
    st.subheader("🌐 Network Health Overview")
    chart_left, chart_right = st.columns(2)

    with chart_left:
        status_counts = df["status"].value_counts().rename_axis("Status").reset_index(name="Count")
        st.markdown("**Network Status Distribution**")
        st.bar_chart(status_counts, x="Status", y="Count")

    with chart_right:
        type_counts = df["check_type"].value_counts().rename_axis("Monitoring Type").reset_index(name="Count")
        st.markdown("**Monitoring Activity Breakdown**")
        st.bar_chart(type_counts, x="Monitoring Type", y="Count")

    st.divider()
    st.subheader("📋 Recent Monitoring Activity")
    st.dataframe(
        df[["device_ip", "check_type", "status", "latency_ms", "checked_at"]].head(10),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# PAGE 2: DEVICE MONITORING
# ============================================================

elif selected_page == "Device Monitoring":
    st.header("📡 Device Health & Availability")
    st.caption("Review the latest device state, run reachability checks, and filter devices.")

    if st.button("🔍 Run Health Check"):
        run_health_checks(df)
        st.rerun()

    health_data = df[
        df["check_type"].isin(["DISCOVERY", "REACHABILITY"])
    ].sort_values("id", ascending=False)

    if health_data.empty:
        st.info("No device discovery or reachability records are available.")
    else:
        latest_devices = health_data.drop_duplicates(subset=["device_ip"]).copy()
        latest_devices["Device Status"] = latest_devices["status"].map(
            {"ONLINE": "🟢 ONLINE", "OFFLINE": "🔴 OFFLINE"}
        ).fillna("🟡 UNKNOWN")

        check_counts = (
            df.groupby("device_ip").size().reset_index(name="Total Checks")
        )
        latest_devices = latest_devices.merge(check_counts, on="device_ip", how="left")

        device_table = latest_devices[
            ["device_ip", "Device Status", "Total Checks", "checked_at"]
        ].rename(
            columns={
                "device_ip": "IP Address",
                "checked_at": "Last Checked",
            }
        )

        search_ip = st.text_input(
            "🔍 Search Device IP",
            placeholder="Enter an IP address...",
            key="device_search",
        )
        status_filter = st.selectbox(
            "Filter by Device Status",
            ["ALL", "🟢 ONLINE", "🔴 OFFLINE", "🟡 UNKNOWN"],
            key="device_status_filter",
        )

        filtered_devices = device_table.copy()
        if search_ip:
            filtered_devices = filtered_devices[
                filtered_devices["IP Address"].str.contains(
                    search_ip, case=False, na=False
                )
            ]
        if status_filter != "ALL":
            filtered_devices = filtered_devices[
                filtered_devices["Device Status"] == status_filter
            ]

        st.dataframe(filtered_devices, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📊 Device Availability Analytics")
    if not device_availability.empty:
        availability_display = device_availability.rename(
            columns={
                "device_ip": "IP Address",
                "total_checks": "Total Checks",
                "successful_checks": "Successful Checks",
            }
        )
        st.dataframe(
            availability_display[
                ["IP Address", "Total Checks", "Successful Checks", "Availability (%)"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No reachability history is available for availability calculations.")

    st.divider()
    st.subheader("🔌 Device Service Details")
    device_options = sorted(df["device_ip"].dropna().unique().tolist())
    if device_options:
        selected_device = st.selectbox(
            "Select Device for Service Details",
            device_options,
            key="device_service_details_select",
        )
        service_rows = df[
            (df["device_ip"] == selected_device)
            & (df["check_type"] == "SERVICE_ENUMERATION")
        ].copy()
        if not service_rows.empty:
            service_rows["Port"] = service_rows["details"].str.extract(r"Port (\d+)")
            service_rows["Service"] = service_rows["details"].str.extract(r"Port \d+ - (.*)")
            st.dataframe(
                service_rows[["Port", "Service", "status", "checked_at"]].rename(
                    columns={"status": "Status", "checked_at": "Last Checked"}
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No service enumeration records are available for this device.")
    else:
        st.info("No device records are available.")


# ============================================================
# PAGE 3: ALERTS CENTER
# ============================================================

elif selected_page == "Alerts Center":
    st.header("🚨 Security & Alert Center")
    st.caption("Review active incidents, acknowledge alerts, and filter alert history.")

    if alerts_df.empty:
        st.info("No alerts are available.")
    else:
        unacknowledged = alerts_df[
            (alerts_df["status"] == "ACTIVE")
            & (pd.to_numeric(alerts_df["acknowledged"], errors="coerce").fillna(0) == 0)
        ]

        st.subheader("Acknowledge Active Alerts")
        if unacknowledged.empty:
            st.success("There are no unacknowledged active alerts.")
        else:
            for _, alert_row in unacknowledged.iterrows():
                alert_col, action_col = st.columns([5, 1])
                with alert_col:
                    st.write(f"**{alert_row['device_ip']}** — {alert_row['message']}")
                    st.caption(
                        f"Severity: {alert_row['severity']} | "
                        f"Created: {alert_row['created_at']}"
                    )
                with action_col:
                    if st.button("Acknowledge", key=f"ack_alert_{alert_row['id']}"):
                        acknowledge_device_alert(int(alert_row["id"]))
                        st.success("Alert acknowledged.")
                        st.rerun()

        st.divider()
        st.subheader("Alert History")
        filter_cols = st.columns(3)

        status_options = ["All"] + sorted(alerts_df["status"].dropna().unique().tolist())
        severity_options = ["All"] + sorted(alerts_df["severity"].dropna().unique().tolist())
        ack_options = ["All", "Acknowledged", "Unacknowledged"]

        with filter_cols[0]:
            selected_alert_status = st.selectbox("Filter by Status", status_options)
        with filter_cols[1]:
            selected_severity = st.selectbox("Filter by Severity", severity_options)
        with filter_cols[2]:
            selected_ack = st.selectbox("Filter by Acknowledgement", ack_options)

        filtered_alerts = alerts_df.copy()
        if selected_alert_status != "All":
            filtered_alerts = filtered_alerts[
                filtered_alerts["status"] == selected_alert_status
            ]
        if selected_severity != "All":
            filtered_alerts = filtered_alerts[
                filtered_alerts["severity"] == selected_severity
            ]
        if selected_ack == "Acknowledged":
            filtered_alerts = filtered_alerts[
                pd.to_numeric(filtered_alerts["acknowledged"], errors="coerce") == 1
            ]
        elif selected_ack == "Unacknowledged":
            filtered_alerts = filtered_alerts[
                pd.to_numeric(filtered_alerts["acknowledged"], errors="coerce") == 0
            ]

        display_columns = [
            column for column in [
                "device_ip", "alert_type", "severity", "message",
                "status", "acknowledged", "created_at", "resolved_at",
            ]
            if column in filtered_alerts.columns
        ]
        if filtered_alerts.empty:
            st.info("No alerts match the selected filters.")
        else:
            st.dataframe(
                filtered_alerts[display_columns],
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# PAGE 4: PERFORMANCE ANALYTICS
# ============================================================

elif selected_page == "Performance Analytics":
    st.header("📈 Network Performance Analytics")
    st.caption("Track latency trends, device response times, and network reliability.")

    perf_cols = st.columns(4)
    perf_cols[0].metric("Average Latency", f"{average_latency} ms")
    perf_cols[1].metric("Ping Failure Rate", f"{packet_loss}%")
    perf_cols[2].metric("Successful Pings", int((reachability_data["status"] == "ONLINE").sum()))
    perf_cols[3].metric("Failed Pings", failed_ping_checks)

    st.divider()
    st.subheader("📉 Network Latency Trend")
    latency_trend = latency_data.copy()
    if not latency_trend.empty:
        latency_trend["checked_at"] = pd.to_datetime(
            latency_trend["checked_at"], errors="coerce"
        )
        latency_trend = latency_trend.dropna(subset=["checked_at"]).sort_values("checked_at")
        if not latency_trend.empty:
            st.line_chart(latency_trend.set_index("checked_at")["latency_ms"])
        else:
            st.info("No valid timestamps are available for latency charting.")
    else:
        st.info("No successful latency measurements are available yet.")

    st.divider()
    st.subheader("📊 Device Performance Comparison")
    if not latency_data.empty:
        performance = (
            latency_data.groupby("device_ip")
            .agg(
                Average_Latency=("latency_ms", "mean"),
                Successful_Checks=("latency_ms", "count"),
            )
            .reset_index()
        )
        performance["Average_Latency"] = performance["Average_Latency"].round(2)
        st.bar_chart(
            performance.set_index("device_ip")["Average_Latency"],
            horizontal=True,
        )
        st.dataframe(
            performance.rename(
                columns={
                    "device_ip": "IP Address",
                    "Average_Latency": "Average Latency (ms)",
                    "Successful_Checks": "Successful Checks",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No device performance data is available yet.")

    st.divider()
    st.subheader("📊 Availability by Device")
    if not device_availability.empty:
        availability_chart = device_availability.set_index("device_ip")["Availability (%)"]
        st.bar_chart(availability_chart)
    else:
        st.info("No device availability data is available.")


# ============================================================
# PAGE 5: NETWORK TOPOLOGY
# ============================================================

elif selected_page == "Network Topology":
    st.header("🌐 Network Topology & Route Analysis")
    st.caption("Review recorded route discovery and traceroute information.")

    topology_df = load_topology()
    if topology_df.empty:
        st.info("No successful topology records are available. Run Map Topology from the CLI first.")
    else:
        for _, topology_row in topology_df.iterrows():
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;justify-content:center;
                    gap:20px;flex-wrap:wrap;margin:12px 0;">
                    <div style="background:#163b5c;padding:18px;border-radius:12px;text-align:center;">
                        💻<br><b>Source</b><br>127.0.0.1
                    </div>
                    <div style="font-size:28px;color:#38bdf8;">➜</div>
                    <div style="background:#164d3b;padding:18px;border-radius:12px;text-align:center;">
                        🌐<br><b>Destination</b><br>{topology_row['device_ip']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander(f"Traceroute: {topology_row['device_ip']}"):
                st.code(str(topology_row["details"]))
                st.caption(f"Last checked: {topology_row['checked_at']}")

    st.divider()
    st.subheader("Topology Monitoring Records")
    topology_records = df[df["check_type"] == "TOPOLOGY"]
    if topology_records.empty:
        st.info("No topology monitoring records are available.")
    else:
        st.dataframe(
            topology_records[["device_ip", "status", "details", "checked_at"]],
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# PAGE 6: SERVICE AND SNMP
# ============================================================

elif selected_page == "Service & SNMP":
    st.header("🔌 Service Discovery & SNMP Monitoring")
    st.caption("Inspect discovered services, open ports, and SNMP polling results.")

    st.subheader("Service Discovery & Port Analysis")
    services = df[df["check_type"] == "SERVICE_ENUMERATION"]
    if services.empty:
        st.info("No service enumeration records are available.")
    else:
        st.dataframe(
            services[["device_ip", "details", "status", "checked_at"]],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("📡 SNMP Device Monitoring")
    snmp_records = df[df["check_type"] == "SNMP"]
    if snmp_records.empty:
        st.info("No SNMP records are available.")
    else:
        st.dataframe(
            snmp_records[["device_ip", "status", "details", "checked_at"]],
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# REPORT HELPERS
# ============================================================

def create_excel_report(data):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary = pd.DataFrame(
            {
                "Metric": [
                    "Total Records",
                    "Unique Devices",
                    "Online Records",
                    "Offline Records",
                    "Open Ports",
                ],
                "Value": [
                    len(data),
                    data["device_ip"].nunique(),
                    int((data["status"] == "ONLINE").sum()),
                    int((data["status"] == "OFFLINE").sum()),
                    int(
                        (
                            (data["check_type"] == "SERVICE_ENUMERATION")
                            & (data["status"] == "OPEN")
                        ).sum()
                    ),
                ],
            }
        )
        summary.to_excel(writer, sheet_name="NMS Summary", index=False)
        data.to_excel(writer, sheet_name="Monitoring History", index=False)

        for worksheet in writer.sheets.values():
            worksheet.freeze_panes = "A2"
            for cell in worksheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(fill_type="solid", fgColor="17365D")
                cell.alignment = Alignment(horizontal="center")
            for column_cells in worksheet.columns:
                column_letter = get_column_letter(column_cells[0].column)
                max_length = max(len(str(cell.value or "")) for cell in column_cells)
                worksheet.column_dimensions[column_letter].width = min(max_length + 3, 55)

    output.seek(0)
    return output.getvalue()


def create_pdf_report(data):
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("NMS NETWORK MONITORING SYSTEM", styles["Title"]),
        Paragraph("Professional Network Diagnostic & Monitoring Report", styles["Heading2"]),
        Spacer(1, 10),
        Paragraph(
            f"Report Generated: {pd.Timestamp.now().strftime('%d-%m-%Y %H:%M:%S')}",
            styles["Normal"],
        ),
        Paragraph(f"Devices Included: {data['device_ip'].nunique()}", styles["Normal"]),
        Paragraph(f"Total Monitoring Records: {len(data)}", styles["Normal"]),
        Spacer(1, 16),
    ]

    headers = ["ID", "Device IP", "Check Type", "Status", "Details", "Latency", "Checked At"]
    table_data = [headers]
    for _, row in data.iterrows():
        details_text = str(row.get("details", "") or "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        table_data.append(
            [
                str(row.get("id", "")),
                str(row.get("device_ip", "")),
                str(row.get("check_type", "")),
                str(row.get("status", "")),
                Paragraph(details_text, styles["BodyText"]),
                str(row.get("latency_ms", "-") if pd.notna(row.get("latency_ms")) else "-"),
                str(row.get("checked_at", "")),
            ]
        )

    report_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[30, 75, 100, 75, 260, 50, 100],
    )
    report_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF0F6")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(report_table)
    document.build(elements)
    output.seek(0)
    return output.getvalue()


# ============================================================
# PAGE 7: REPORTS
# ============================================================

if selected_page == "Reports":
    st.header("📊 NMS Report Center")
    st.caption("Filter monitoring records and export professional reports.")

    report_devices = ["ALL"] + sorted(df["device_ip"].dropna().unique().tolist())
    report_types = ["ALL"] + sorted(df["check_type"].dropna().unique().tolist())

    filter_cols = st.columns(2)
    with filter_cols[0]:
        report_device = st.selectbox("Select Device", report_devices, key="report_device")
    with filter_cols[1]:
        report_type = st.selectbox("Select Monitoring Type", report_types, key="report_type")

    report_df = df.copy()
    if report_device != "ALL":
        report_df = report_df[report_df["device_ip"] == report_device]
    if report_type != "ALL":
        report_df = report_df[report_df["check_type"] == report_type]

    report_dates = pd.to_datetime(report_df["checked_at"], errors="coerce").dropna()
    if not report_dates.empty:
        date_range = st.date_input(
            "Select Report Date Range",
            value=(report_dates.min().date(), report_dates.max().date()),
            min_value=report_dates.min().date(),
            max_value=report_dates.max().date(),
            key="report_date_range",
        )
        if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            start_date, end_date = date_range
            date_values = pd.to_datetime(report_df["checked_at"], errors="coerce")
            report_df = report_df[
                (date_values.dt.date >= start_date)
                & (date_values.dt.date <= end_date)
            ]
    else:
        st.warning("No valid monitoring dates are available for the selected filters.")

    st.metric("Records Selected for Report", len(report_df))
    st.dataframe(report_df, use_container_width=True, hide_index=True)

    if report_df.empty:
        st.warning("No records match the selected report filters.")
    else:
        export_df = report_df.copy()
        export_df["checked_at"] = pd.to_datetime(
            export_df["checked_at"], errors="coerce"
        ).dt.strftime("%d-%m-%Y %H:%M:%S")
        export_df = export_df.astype(object).where(pd.notna(export_df), "")

        csv_data = export_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        json_data = export_df.to_json(
            orient="records", indent=4, force_ascii=False
        ).encode("utf-8")
        excel_data = create_excel_report(export_df)
        pdf_data = create_pdf_report(export_df)

        st.subheader("📥 Download NMS Monitoring Reports")
        download_cols = st.columns(2)
        with download_cols[0]:
            st.download_button(
                "📊 Download Excel Report",
                data=excel_data,
                file_name="NMS_Monitoring_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.download_button(
                "📋 Download CSV Report",
                data=csv_data,
                file_name="NMS_Monitoring_Report.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with download_cols[1]:
            st.download_button(
                "📄 Download PDF Report",
                data=pdf_data,
                file_name="NMS_Monitoring_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            st.download_button(
                "💻 Download JSON Report",
                data=json_data,
                file_name="NMS_Monitoring_Report.json",
                mime="application/json",
                use_container_width=True,
            )


# ============================================================
# PROFESSIONAL FOOTER
# ============================================================

st.markdown(
    """
    <div class="nms-footer">
        NMS Network Operations Center
        &nbsp;•&nbsp; Network Monitoring & Diagnostics
        &nbsp;•&nbsp; Enterprise NOC Interface
    </div>
    """,
    unsafe_allow_html=True,
)

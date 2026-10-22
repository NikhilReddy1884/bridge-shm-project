"""
Bridge Earthquake & SHM Dashboard - FRESH CLEAN VERSION
Run with: streamlit run dashboard_fresh.py

Matches the Arduino sketch that sends 3 values per line:
vibration,pzt1,pzt2
"""

import streamlit as st
import serial
import sqlite3
import numpy as np
import pandas as pd
import time

# ---------- CONFIG ----------
SERIAL_PORT = "COM4"        # change if your port is different
BAUD_RATE = 115200
DB_NAME = "bridge_data_fresh.db"   # brand new file, no old schema conflicts
THRESHOLD = 1.3
MAX_VALID_G = 8.0

# ---------- DBMS: SQLite setup ----------
def setup_database():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vibration REAL,
            pzt1 REAL,
            pzt2 REAL,
            timestamp TEXT
        )
    """)
    conn.commit()
    return conn

conn = setup_database()

# ---------- DS: in-memory buffers ----------
MAX_POINTS = 100
if "vibration_history" not in st.session_state:
    st.session_state.vibration_history = []
if "pzt1_history" not in st.session_state:
    st.session_state.pzt1_history = []
if "pzt2_history" not in st.session_state:
    st.session_state.pzt2_history = []
if "healthy_baseline" not in st.session_state:
    st.session_state.healthy_baseline = {"pzt1": [], "pzt2": []}
if "damaged_readings" not in st.session_state:
    st.session_state.damaged_readings = {"pzt1": [], "pzt2": []}
if "gate_closed" not in st.session_state:
    st.session_state.gate_closed = False

# ---------- Serial connection ----------
@st.cache_resource
def get_serial_connection():
    try:
        return serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    except Exception as e:
        return None

ser = get_serial_connection()

def read_one_line():
    """Returns (vibration, pzt1, pzt2) or None."""
    if ser is None:
        return None
    try:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
    except Exception:
        return None
    if not line:
        return None
    parts = line.split(",")
    if len(parts) != 3:
        return None  # skip startup messages
    try:
        vib, p1, p2 = map(float, parts)
    except ValueError:
        return None
    if vib > MAX_VALID_G or vib < 0:
        return None
    return vib, p1, p2

def read_peak(num_samples=8):
    """Reads several lines quickly, returns the one with highest vibration."""
    best = None
    best_mag = -1
    for _ in range(num_samples):
        r = read_one_line()
        if r and r[0] > best_mag:
            best_mag = r[0]
            best = r
    return best

def save_to_db(vib, p1, p2):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO readings (vibration, pzt1, pzt2, timestamp) VALUES (?, ?, ?, datetime('now'))",
        (vib, p1, p2)
    )
    conn.commit()

def calculate_rmsd(healthy, damaged):
    healthy = np.array(healthy)
    damaged = np.array(damaged)
    n = min(len(healthy), len(damaged))
    if n == 0:
        return 0.0
    healthy, damaged = healthy[:n], damaged[:n]
    numerator = np.sum((damaged - healthy) ** 2)
    denominator = np.sum(healthy ** 2)
    if denominator == 0:
        return 0.0
    return float(np.sqrt(numerator / denominator) * 100)

# ---------- PAGE LAYOUT ----------
st.set_page_config(page_title="Bridge Monitoring Dashboard", layout="wide")
st.title("Bridge Earthquake & Structural Health Monitoring Dashboard")

if ser is None:
    st.error(f"Could not open {SERIAL_PORT}. Make sure: Arduino IDE is fully closed, "
             f"no other terminal is running this script, and the ESP32 is plugged in. "
             f"Then stop this (Ctrl+C in terminal) and run it again.")
    st.stop()

reading = read_peak(8)

if reading:
    vib, p1, p2 = reading
    save_to_db(vib, p1, p2)

    st.session_state.vibration_history.append(vib)
    st.session_state.pzt1_history.append(p1)
    st.session_state.pzt2_history.append(p2)
    st.session_state.vibration_history = st.session_state.vibration_history[-MAX_POINTS:]
    st.session_state.pzt1_history = st.session_state.pzt1_history[-MAX_POINTS:]
    st.session_state.pzt2_history = st.session_state.pzt2_history[-MAX_POINTS:]

    if vib > THRESHOLD:
        st.session_state.gate_closed = True

tab1, tab2, tab3 = st.tabs(["Earthquake Detection", "Structural Health Monitoring (SHM)", "Stored Data (DBMS)"])

with tab1:
    st.subheader("Live Vibration Reading (MPU6050)")
    if reading:
        vib = st.session_state.vibration_history[-1]
        col1, col2, col3 = st.columns(3)
        col1.metric("Current vibration (g)", f"{vib:.3f}")

        if vib > THRESHOLD:
            col2.error("ALERT: Threshold exceeded!")
        else:
            col2.success("Normal")

        if st.session_state.gate_closed:
            col3.warning("GATE: CLOSED")
        else:
            col3.info("GATE: OPEN")

        if st.button("Reset gate (open again)"):
            if ser:
                ser.write(b'R')
                ser.flush()
                st.success("Reset command sent!")
            st.session_state.gate_closed = False
            time.sleep(0.3)

        st.line_chart(pd.DataFrame({"Vibration (g)": st.session_state.vibration_history}))
    else:
        st.warning("No data yet. Waiting for ESP32...")

with tab2:
    st.subheader("Live PZT Sensor Readings")
    if reading:
        c1, c2 = st.columns(2)
        c1.metric("PZT Sensor 1 (V)", f"{st.session_state.pzt1_history[-1]:.4f}")
        c2.metric("PZT Sensor 2 (V)", f"{st.session_state.pzt2_history[-1]:.4f}")

        st.line_chart(pd.DataFrame({
            "PZT Sensor 1": st.session_state.pzt1_history,
            "PZT Sensor 2": st.session_state.pzt2_history
        }))

    st.divider()
    st.subheader("RMSD Damage Analysis")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Record HEALTHY baseline (50 samples)"):
            with st.spinner("Collecting healthy baseline..."):
                buffer1, buffer2 = [], []
                attempts = 0
                while len(buffer1) < 50 and attempts < 500:
                    r = read_one_line()
                    if r:
                        _, p1, p2 = r
                        buffer1.append(p1)
                        buffer2.append(p2)
                    attempts += 1
                st.session_state.healthy_baseline = {"pzt1": buffer1, "pzt2": buffer2}
            st.success(f"Captured {len(buffer1)} healthy samples.")

    with col_b:
        if st.button("Record DAMAGED test (50 samples)"):
            with st.spinner("Collecting post-damage readings..."):
                buffer1, buffer2 = [], []
                attempts = 0
                while len(buffer1) < 50 and attempts < 500:
                    r = read_one_line()
                    if r:
                        _, p1, p2 = r
                        buffer1.append(p1)
                        buffer2.append(p2)
                    attempts += 1
                st.session_state.damaged_readings = {"pzt1": buffer1, "pzt2": buffer2}
            st.success(f"Captured {len(buffer1)} damaged-state samples.")

    if st.session_state.healthy_baseline["pzt1"] and st.session_state.damaged_readings["pzt1"]:
        rmsd1 = calculate_rmsd(st.session_state.healthy_baseline["pzt1"], st.session_state.damaged_readings["pzt1"])
        rmsd2 = calculate_rmsd(st.session_state.healthy_baseline["pzt2"], st.session_state.damaged_readings["pzt2"])

        st.bar_chart(pd.DataFrame({"RMSD (%)": [rmsd1, rmsd2]}, index=["Sensor 1", "Sensor 2"]))

        likely = "Sensor 1" if rmsd1 > rmsd2 else "Sensor 2"
        st.info(f"Likely damage location: near {likely} (higher RMSD change)")

with tab3:
    st.subheader("All Readings Stored in SQLite Database")
    df = pd.read_sql_query("SELECT * FROM readings ORDER BY id DESC LIMIT 200", conn)
    st.dataframe(df, use_container_width=True)
    total = pd.read_sql_query("SELECT COUNT(*) as c FROM readings", conn)["c"][0]
    st.caption(f"Total rows stored: {total}")

time.sleep(1)
st.rerun()
# Bridge Earthquake Detection & Structural Health Monitoring System

A combined IoT prototype that detects seismic vibrations and monitors 
structural health of a model bridge in real time.

## Features
- Earthquake detection using MPU6050 (ESP32-C3)
- Automatic servo-controlled safety gate on threshold trigger
- Structural Health Monitoring using 2 PZT sensors + ADS1115
- RMSD-based damage detection and localization
- Live dashboard (Streamlit) with SQLite data logging

## Tech Stack
- **Hardware:** ESP32-C3, MPU6050, PZT sensors, ADS1115, SG90 servo
- **Firmware:** Arduino (C++)
- **Software:** Python (Streamlit, NumPy, SQLite)

## How it works
1. ESP32 reads vibration and PZT sensor data continuously
2. If vibration crosses a threshold, a servo gate closes automatically
3. Python dashboard reads live data via Serial, stores it in SQLite, 
   and calculates RMSD between healthy and damaged sensor readings 
   to estimate damage location

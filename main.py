# app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib
import json
import time
from typing import Dict, List
import os

# Initialize session state variables
def init_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'current_deck' not in st.session_state:
        st.session_state.current_deck = None
    if 'progress' not in st.session_state:
        st.session_state.progress = {}
    if 'daily_stats' not in st.session_state:
        st.session_state.daily_stats = {'reviewed': 0, 'new': 0}

class Card:
    def __init__(self, front: str, back: str, audio_path: str):
        self.front = front
        self.back = back
        self.audio_path = audio_path
        self.interval = 1
        self.next_review = datetime.now()
        self.ease_factor = 2.5

def load_user_data(username: str) -> Dict:
    if os.path.exists(f"data/{username}_progress.json"):
        with open(f"data/{username}_progress.json", 'r') as f:
            return json.load(f)
    return {}

def save_user_data(username: str, data: Dict):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{username}_progress.json", 'w') as f:
        json.dump(data, f)

def verify_password(username: str, password: str) -> bool:
    return username == "yigit" and password == "12345678"

def calculate_next_review(interval: int, quality: str) -> datetime:
    if quality == "again":
        return datetime.now() + timedelta(minutes=10)
    else:  # "good"
        return datetime.now() + timedelta(days=interval * 2)

def main():
    st.set_page_config(page_title="🎧 Listening Practice", layout="wide")
    init_session_state()

    # Login Section
    if not st.session_state.logged_in:
        st.markdown("# 🎧 Welcome to Listening Practice!")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login 🔐")
            
            if submit:
                if verify_password(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.progress = load_user_data(username)
                    st.experimental_rerun()
                else:
                    st.error("❌ Invalid credentials")
        return

    # Main App Interface
    st.sidebar.markdown("## ⚙️ Settings")
    daily_new = st.sidebar.number_input("New cards per day", 1, 50, 20)
    daily_review = st.sidebar.number_input("Review cards per day", 1, 100, 50)
    
    intervals = st.sidebar.multiselect(
        "Review intervals (days)",
        options=[1, 2, 4, 7, 14, 30],
        default=[1, 4, 7]
    )

    # Main practice area
    st.markdown("# 🎧 Listening Practice")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Current Card")
        if st.button("▶️ Play Audio"):
            # Simulate audio playback
            st.audio("sample_audio.mp3")  # Replace with actual audio path
        
        user_input = st.text_area("Type what you hear:", height=100)
        
        col_again, col_good = st.columns(2)
        with col_again:
            if st.button("🔄 Again", use_container_width=True):
                st.session_state.daily_stats['reviewed'] += 1
                # Update card scheduling logic here
        with col_good:
            if st.button("✅ Good", use_container_width=True):
                st.session_state.daily_stats['reviewed'] += 1
                # Update card scheduling logic here

    with col2:
        st.markdown("### Daily Progress")
        st.metric("Reviews Done", f"{st.session_state.daily_stats['reviewed']}/{daily_review}")
        st.metric("New Cards", f"{st.session_state.daily_stats['new']}/{daily_new}")
        
        # Progress bar
        progress = st.session_state.daily_stats['reviewed'] / daily_review
        st.progress(progress)
        
        if st.button("💾 Save Progress"):
            save_user_data(st.session_state.username, st.session_state.progress)
            st.success("Progress saved successfully! 🎉")

if __name__ == "__main__":
    main()

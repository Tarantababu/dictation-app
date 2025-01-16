import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib
import json
import time
import sqlite3
import zipfile
import io
from typing import Dict, List, Tuple
import os

# Add Anki deck parsing functionality
def parse_anki_deck(uploaded_file) -> List[Dict]:
    """Parse uploaded Anki deck (.apkg file) and extract cards"""
    cards = []
    
    # Create a temporary directory to extract the .apkg file
    temp_dir = "temp_anki"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Extract the .apkg file (which is a SQLite database)
        with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Connect to the SQLite database
        conn = sqlite3.connect(f"{temp_dir}/collection.anki2")
        cursor = conn.cursor()
        
        # Get notes (cards) from the database
        cursor.execute("""
            SELECT notes.id, notes.flds, notes.tags, cards.due 
            FROM notes 
            JOIN cards ON cards.nid = notes.id
        """)
        
        for row in cursor.fetchall():
            note_id, fields, tags, due = row
            # Split fields (typically separated by \x1f character in Anki)
            fields_list = fields.split('\x1f')
            
            # Assuming first field is front (sentence + audio) and second is back (translation)
            if len(fields_list) >= 2:
                # Extract audio file name if present (Anki stores audio references like [sound:filename.mp3])
                front = fields_list[0]
                audio_file = None
                if '[sound:' in front:
                    import re
                    audio_match = re.search(r'\[sound:(.*?)\]', front)
                    if audio_match:
                        audio_file = audio_match.group(1)
                        front = re.sub(r'\[sound:.*?\]', '', front).strip()
                
                cards.append({
                    'id': note_id,
                    'front': front,
                    'back': fields_list[1],
                    'audio_file': audio_file,
                    'tags': tags,
                    'due': due
                })
        
        conn.close()
        
        # Also extract media files
        if os.path.exists(f"{temp_dir}/media"):
            with open(f"{temp_dir}/media", 'r') as f:
                media_dict = json.load(f)
                # TODO: Process media files if needed
    
    except Exception as e:
        st.error(f"Error parsing Anki deck: {str(e)}")
        cards = []
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return cards

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
    if 'decks' not in st.session_state:
        st.session_state.decks = {}

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
    
    # Deck Upload Section in Sidebar
    st.sidebar.markdown("### 📚 Deck Management")
    uploaded_file = st.sidebar.file_uploader("Upload Anki Deck (.apkg)", type=['apkg'])
    if uploaded_file:
        with st.sidebar.spinner("Processing deck..."):
            cards = parse_anki_deck(uploaded_file)
            if cards:
                deck_name = uploaded_file.name.replace('.apkg', '')
                st.session_state.decks[deck_name] = cards
                st.sidebar.success(f"✅ Successfully imported {len(cards)} cards!")
    
    # Deck Selection
    if st.session_state.decks:
        selected_deck = st.sidebar.selectbox(
            "Select Deck",
            options=list(st.session_state.decks.keys())
        )
        st.session_state.current_deck = selected_deck
    
    daily_new = st.sidebar.number_input("New cards per day", 1, 50, 20)
    daily_review = st.sidebar.number_input("Review cards per day", 1, 100, 50)
    
    intervals = st.sidebar.multiselect(
        "Review intervals (days)",
        options=[1, 2, 4, 7, 14, 30],
        default=[1, 4, 7]
    )

    # Main practice area
    st.markdown("# 🎧 Listening Practice")
    
    if not st.session_state.current_deck:
        st.info("👆 Please upload and select an Anki deck to start practicing!")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Current Card")
        current_cards = st.session_state.decks[st.session_state.current_deck]
        if current_cards:
            current_card = current_cards[0]  # For demonstration, you'd want to implement proper card selection
            
            st.markdown(f"**Translation:** {current_card['back']}")  # Show translation (hidden in real app)
            
            if current_card['audio_file']:
                if st.button("▶️ Play Audio"):
                    # Handle audio playback
                    st.audio(current_card['audio_file'])
            
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
        
        # Deck Statistics
        if st.session_state.current_deck:
            st.markdown("### Deck Statistics")
            total_cards = len(st.session_state.decks[st.session_state.current_deck])
            st.metric("Total Cards", total_cards)
        
        if st.button("💾 Save Progress"):
            save_user_data(st.session_state.username, st.session_state.progress)
            st.success("Progress saved successfully! 🎉")

if __name__ == "__main__":
    main()

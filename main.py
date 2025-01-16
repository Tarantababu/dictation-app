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
import tempfile
import shutil

# Add Anki deck parsing functionality
def parse_anki_deck(uploaded_file) -> List[Dict]:
    """Parse uploaded Anki deck (.apkg file) and extract cards"""
    cards = []
    
    # Create a temporary directory using tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Save the uploaded file to a temporary file
            temp_apkg_path = os.path.join(temp_dir, "temp.apkg")
            with open(temp_apkg_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Extract the .apkg file
            with zipfile.ZipFile(temp_apkg_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Check if collection.anki2 exists
            collection_path = os.path.join(temp_dir, "collection.anki2")
            if not os.path.exists(collection_path):
                st.error("Invalid Anki deck file: collection.anki2 not found")
                return []
            
            # Connect to the SQLite database
            conn = sqlite3.connect(collection_path)
            cursor = conn.cursor()
            
            try:
                # Get notes (cards) from the database
                cursor.execute("""
                    SELECT notes.id, notes.flds, notes.tags
                    FROM notes
                """)
                
                for row in cursor.fetchall():
                    note_id, fields, tags = row
                    # Split fields (typically separated by \x1f character in Anki)
                    fields_list = fields.split('\x1f')
                    
                    # Assuming first field is front (sentence + audio) and second is back (translation)
                    if len(fields_list) >= 2:
                        # Extract audio file name if present
                        front = fields_list[0]
                        audio_file = None
                        if '[sound:' in front:
                            import re
                            audio_match = re.search(r'\[sound:(.*?)\]', front)
                            if audio_match:
                                audio_file = audio_match.group(1)
                                front = re.sub(r'\[sound:.*?\]', '', front).strip()
                        
                        card_data = {
                            'id': str(note_id),  # Convert to string to ensure JSON serializable
                            'front': front.strip(),
                            'back': fields_list[1].strip(),
                            'audio_file': audio_file,
                            'tags': tags,
                            'due': datetime.now().isoformat()  # Add a default due date
                        }
                        cards.append(card_data)
                
            except sqlite3.Error as e:
                st.error(f"Database error: {str(e)}")
                return []
            finally:
                conn.close()
            
            # Handle media files if they exist
            media_file = os.path.join(temp_dir, "media")
            if os.path.exists(media_file):
                try:
                    with open(media_file, 'r') as f:
                        media_dict = json.load(f)
                        # Store media information in session state for later use
                        st.session_state.media_files = media_dict
                except json.JSONDecodeError:
                    st.warning("Could not parse media file information")
                except Exception as e:
                    st.warning(f"Error processing media files: {str(e)}")
            
        except zipfile.BadZipFile:
            st.error("Invalid .apkg file: The file is not a valid Anki deck package")
            return []
        except Exception as e:
            st.error(f"Error processing Anki deck: {str(e)}")
            return []
    
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
    if 'media_files' not in st.session_state:
        st.session_state.media_files = {}

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

def get_next_card(deck: List[Dict]) -> Dict:
    """Get the next card to review based on due date"""
    if not deck:
        return None
    
    # For now, just return the first card
    # In a full implementation, you'd want to sort by due date and handle new vs review cards
    return deck[0]

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
        try:
            with st.sidebar.spinner("Processing deck..."):
                cards = parse_anki_deck(uploaded_file)
                if cards:
                    deck_name = uploaded_file.name.replace('.apkg', '')
                    st.session_state.decks[deck_name] = cards
                    st.sidebar.success(f"✅ Successfully imported {len(cards)} cards!")
        except Exception as e:
            st.sidebar.error(f"Error uploading deck: {str(e)}")
    
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
        if st.session_state.current_deck and st.session_state.decks[st.session_state.current_deck]:
            current_card = get_next_card(st.session_state.decks[st.session_state.current_deck])
            
            if current_card:
                st.markdown(f"**Translation:** {current_card['back']}")
                
                if current_card['audio_file']:
                    if st.button("▶️ Play Audio"):
                        # Here you would implement actual audio playback
                        st.info(f"Audio file: {current_card['audio_file']}")
                
                user_input = st.text_area("Type what you hear:", height=100)
                
                col_again, col_good = st.columns(2)
                with col_again:
                    if st.button("🔄 Again", use_container_width=True):
                        st.session_state.daily_stats['reviewed'] += 1
                with col_good:
                    if st.button("✅ Good", use_container_width=True):
                        st.session_state.daily_stats['reviewed'] += 1

    with col2:
        st.markdown("### Daily Progress")
        st.metric("Reviews Done", f"{st.session_state.daily_stats['reviewed']}/{daily_review}")
        st.metric("New Cards", f"{st.session_state.daily_stats['new']}/{daily_new}")
        
        progress = st.session_state.daily_stats['reviewed'] / daily_review
        st.progress(progress)
        
        if st.session_state.current_deck:
            st.markdown("### Deck Statistics")
            total_cards = len(st.session_state.decks[st.session_state.current_deck])
            st.metric("Total Cards", total_cards)
        
        if st.button("💾 Save Progress"):
            save_user_data(st.session_state.username, st.session_state.progress)
            st.success("Progress saved successfully! 🎉")

if __name__ == "__main__":
    main()

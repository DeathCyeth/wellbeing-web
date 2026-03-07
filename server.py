#!/usr/bin/env python3
"""
Simple Flask backend server for Wellbeing Companion Web App
Run this with: python server.py
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
import os
import uuid
import string
import random
from datetime import datetime

# OpenAI integration (optional - install with: pip install openai)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI not installed. AI features will not work.")
    print("Install with: pip install openai")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database file
DB_NAME = "wellbeing.db"

# Directory containing this script (for serving frontend when deployed)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALLOWED_STATIC = {'index.html', 'styles.css', 'app.js', 'api-service.js', 'logo.png', 'favicon.ico'}

def generate_patient_id():
    """Generate a unique numerical patient ID"""
    # Generate a random 6-digit number
    while True:
        # Generate number between 100000 and 999999
        patient_id = random.randint(100000, 999999)
        # Check if it's already taken
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE patient_id=?", (str(patient_id),))
        if not cursor.fetchone():
            conn.close()
            return str(patient_id)
        conn.close()

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            patient_id TEXT UNIQUE,
            age INTEGER
        )
    """)
    
    # Add patient_id column to existing tables if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN patient_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add unique constraint if it doesn't exist (SQLite doesn't support ADD CONSTRAINT, so we'll handle uniqueness in code)
    try:
        # Check if unique index exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_patient_id_unique'")
        if not cursor.fetchone():
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_patient_id_unique ON users(patient_id) WHERE patient_id IS NOT NULL")
    except sqlite3.OperationalError:
        pass
    
    # Add age column to existing tables if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN age INTEGER")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Generate patient_id for existing users who don't have one
    # Also convert old PAT-XXXX format to numerical
    cursor.execute("SELECT username, patient_id FROM users WHERE role='Patient'")
    all_patients = cursor.fetchall()
    for (username, existing_id) in all_patients:
        if not existing_id or existing_id.startswith('PAT-'):
            # Generate new numerical ID
            new_id = generate_patient_id()
            cursor.execute("UPDATE users SET patient_id=? WHERE username=?", (new_id, username))
            print(f"Generated Patient ID {new_id} for {username}")
    
    # Preferences table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            username TEXT PRIMARY KEY,
            likes TEXT,
            dislikes TEXT,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    
    # Notes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    
    # Patient Medical Information table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient_medical_info (
            username TEXT PRIMARY KEY,
            past_medical_history TEXT,
            patient_goals TEXT,
            food_allergies TEXT,
            physical_activity TEXT,
            current_medications TEXT,
            height TEXT,
            weight TEXT,
            sex TEXT,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    
    # Add sex column to users table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN sex TEXT")
    except sqlite3.OperationalError:
        pass
    # New user fields (patient info & search)
    for col, ctype in [
        ("date_of_birth", "TEXT"),
        ("middle_initial", "TEXT"),
        ("last_name", "TEXT"),
        ("biological_sex", "TEXT"),
        ("gender_identity", "TEXT"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {ctype}")
        except sqlite3.OperationalError:
            pass
    # New medical_info fields (biometrics, conditions, lifestyle)
    for col, ctype in [
        ("height_feet", "INTEGER"),
        ("height_inches", "REAL"),
        ("waist_cm", "TEXT"),
        ("hip_cm", "TEXT"),
        ("body_fat_pct", "TEXT"),
        ("lean_mass_kg", "TEXT"),
        ("weight_units", "TEXT"),
        ("height_units", "TEXT"),
        ("diabetes_type", "TEXT"),
        ("chronic_conditions", "TEXT"),
        ("weekly_food_budget", "TEXT"),
        ("activity_level", "TEXT"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE patient_medical_info ADD COLUMN {col} {ctype}")
        except sqlite3.OperationalError:
            pass
    
    conn.commit()
    conn.close()

def _empty_medical_info(sex_default=""):
    """Return empty medical_info dict with all keys (including new biometric/conditions fields)."""
    return {
        "past_medical_history": "",
        "patient_goals": "",
        "food_allergies": "",
        "physical_activity": "",
        "current_medications": "",
        "height": "",
        "weight": "",
        "sex": sex_default,
        "height_feet": None,
        "height_inches": None,
        "waist_cm": "",
        "hip_cm": "",
        "body_fat_pct": "",
        "lean_mass_kg": "",
        "weight_units": "",
        "height_units": "",
        "diabetes_type": "",
        "chronic_conditions": "",
        "weekly_food_budget": "",
        "activity_level": "",
    }


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"})

@app.route('/api/users/login', methods=['POST'])
def login():
    """User login"""
    data = request.get_json()
    username = (data.get('username') or '').strip().lower()
    password = (data.get('password') or '')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, password, name, role, patient_id, age, sex FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = cursor.fetchone()
    
    if user:
        # If patient doesn't have an ID, generate one
        patient_id = user[4] or ""
        if user[3].lower() == 'patient' and not patient_id:
            patient_id = generate_patient_id()
            cursor.execute("UPDATE users SET patient_id=? WHERE username=?", (patient_id, user[0]))
            conn.commit()
            print(f"Generated Patient ID {patient_id} for {user[0]}")
        
        conn.close()
        return jsonify({
            "username": user[0],
            "name": user[2],
            "role": user[3],
            "patient_id": patient_id,
            "age": user[5] if user[5] else None,
            "sex": user[6] if len(user) > 6 and user[6] else ""
        })
    else:
        conn.close()
        return jsonify({"error": "Invalid username or password"}), 401

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user"""
    data = request.get_json()
    username = (data.get('username') or '').strip().lower()
    password = data.get('password', '')
    name = (data.get('name') or '').strip()
    role = (data.get('role') or 'Patient').strip()
    
    if not all([username, password, name]):
        return jsonify({"error": "Username, password, and name are required"}), 400
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Generate patient_id for all users (patients and doctors can have one, but it's mainly for patients)
    patient_id = None
    if role.lower() == 'patient':
        # Keep generating until we get a unique one
        while True:
            new_id = generate_patient_id()
            cursor.execute("SELECT username FROM users WHERE patient_id=?", (new_id,))
            if not cursor.fetchone():
                patient_id = new_id
                break
    
    try:
        cursor.execute(
            "INSERT INTO users (username, password, name, role, patient_id) VALUES (?, ?, ?, ?, ?)",
            (username, password, name, role, patient_id)
        )
        conn.commit()
        conn.close()
        return jsonify({
            "message": "User created successfully",
            "patient_id": patient_id or ""
        }), 201
    except sqlite3.IntegrityError as e:
        conn.close()
        if 'patient_id' in str(e):
            return jsonify({"error": "Error generating patient ID. Please try again."}), 500
        return jsonify({"error": "Username already taken"}), 409

@app.route('/api/users/<username>', methods=['GET'])
def get_user(username):
    """Get user by username"""
    try:
        print(f"GET /api/users/{username} - Starting...")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        print(f"Querying user: {username.lower()}")
        cursor.execute(
            "SELECT username, name, role, patient_id, age, sex, date_of_birth, middle_initial, last_name, biological_sex, gender_identity FROM users WHERE username=?",
            (username.lower(),)
        )
        user = cursor.fetchone()
        if not user:
            conn.close()
            print(f"User {username} not found")
            return jsonify({"error": "User not found"}), 404
        # Pad to 11 elements if old schema
        user = list(user) + [None] * (11 - len(user))
        user = tuple(user[:11])
        print(f"User found: True")
        
        # If patient doesn't have an ID, generate one
        if user[2].lower() == 'patient' and not user[3]:
            print(f"Generating Patient ID for {user[0]}")
            patient_id = generate_patient_id()
            cursor.execute("UPDATE users SET patient_id=? WHERE username=?", (patient_id, user[0]))
            conn.commit()
            user = (user[0], user[1], user[2], patient_id, user[4], user[5], user[6], user[7], user[8], user[9], user[10])
            print(f"Generated Patient ID {patient_id} for {user[0]}")
        
        # Get medical info if user exists
        medical_info = None
        try:
            print("Loading medical info...")
            try:
                cursor.execute(
                    """SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications,
                       height, weight, sex, height_feet, height_inches, waist_cm, hip_cm, body_fat_pct, lean_mass_kg,
                       weight_units, height_units, diabetes_type, chronic_conditions, weekly_food_budget, activity_level
                       FROM patient_medical_info WHERE username=?""",
                    (username.lower(),)
                )
            except sqlite3.OperationalError:
                cursor.execute(
                    "SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications, height, weight, sex FROM patient_medical_info WHERE username=?",
                    (username.lower(),)
                )
            med_data = cursor.fetchone()
            if med_data:
                med_data = list(med_data) + [None] * (20 - len(med_data))
                medical_info = {
                    "past_medical_history": med_data[0] or "",
                    "patient_goals": med_data[1] or "",
                    "food_allergies": med_data[2] or "",
                    "physical_activity": med_data[3] or "",
                    "current_medications": med_data[4] or "",
                    "height": med_data[5] or "",
                    "weight": med_data[6] or "",
                    "sex": med_data[7] or (user[5] if len(user) > 5 and user[5] else ""),
                    "height_feet": med_data[8],
                    "height_inches": med_data[9],
                    "waist_cm": med_data[10] or "",
                    "hip_cm": med_data[11] or "",
                    "body_fat_pct": med_data[12] or "",
                    "lean_mass_kg": med_data[13] or "",
                    "weight_units": med_data[14] or "",
                    "height_units": med_data[15] or "",
                    "diabetes_type": med_data[16] or "",
                    "chronic_conditions": med_data[17] or "",
                    "weekly_food_budget": med_data[18] or "",
                    "activity_level": med_data[19] or "",
                }
            else:
                medical_info = _empty_medical_info(user[5] if len(user) > 5 and user[5] else "")
            print("Medical info loaded")
        except Exception as e:
            print(f"Error loading medical info (non-critical): {e}")
            medical_info = _empty_medical_info(user[5] if len(user) > 5 and user[5] else "")
        
        conn.close()
        
        response_data = {
            "username": user[0],
            "name": user[1],
            "role": user[2],
            "patient_id": user[3] or "",
            "age": user[4] if user[4] else None,
            "sex": medical_info["sex"] if medical_info else (user[5] if len(user) > 5 and user[5] else ""),
            "date_of_birth": user[6] if len(user) > 6 else None,
            "middle_initial": user[7] if len(user) > 7 else None,
            "last_name": user[8] if len(user) > 8 else None,
            "biological_sex": user[9] if len(user) > 9 else (user[5] if len(user) > 5 else None),
            "gender_identity": user[10] if len(user) > 10 else None,
            "medical_info": medical_info
        }
        print(f"Returning user data for {user[0]}")
        return jsonify(response_data)
    except Exception as e:
        print(f"ERROR in get_user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/users/patients', methods=['GET'])
def list_patients():
    """Return all patients for dropdown (username, name, patient_id), ordered by name."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT username, name, patient_id FROM users WHERE role='Patient' ORDER BY LOWER(name), username"
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        cursor.execute(
            "SELECT username, name, patient_id FROM users WHERE role='Patient' ORDER BY name, username"
        )
        rows = cursor.fetchall()
    conn.close()
    return jsonify([{"username": r[0], "name": r[1] or "", "patient_id": r[2] or ""} for r in rows])


@app.route('/api/users/search', methods=['GET'])
def search_users():
    """Search patients by last_name and/or date_of_birth. Query params: last_name, dob (YYYY-MM-DD)."""
    last_name = (request.args.get('last_name') or '').strip()
    dob = (request.args.get('dob') or request.args.get('date_of_birth') or '').strip()
    if not last_name and not dob:
        return jsonify({"error": "Provide at least one of: last_name, dob"}), 400
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT username, name, role, patient_id, age, sex, date_of_birth, middle_initial, last_name, biological_sex, gender_identity FROM users WHERE role='Patient'"
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        cursor.execute("SELECT username, name, role, patient_id, age, sex FROM users WHERE role='Patient'")
        rows = [list(r) + [None] * (11 - len(r)) for r in cursor.fetchall()]
    conn.close()
    results = []
    for row in rows:
        row = list(row) + [None] * (11 - len(row))
        un, name, role, pid, age, sex, row_dob, mi, ln, bio_sex, gender = row[:11]
        if last_name and (not ln or last_name.lower() not in (ln or '').lower()):
            if not (name and last_name.lower() in name.lower()):
                continue
        if dob and (not row_dob or row_dob != dob):
            continue
        results.append({
            "username": un,
            "name": name or "",
            "role": role or "",
            "patient_id": pid or "",
            "age": age,
            "sex": sex or "",
            "date_of_birth": row_dob,
            "middle_initial": mi,
            "last_name": ln,
            "biological_sex": bio_sex or sex,
            "gender_identity": gender,
        })
    return jsonify({"results": results, "count": len(results)})


@app.route('/api/users/by-patient-id/<patient_id>', methods=['GET'])
def get_user_by_patient_id(patient_id):
    """Get user by patient_id (returns same shape as get_user with new fields)."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT username, name, role, patient_id, age, sex, date_of_birth, middle_initial, last_name, biological_sex, gender_identity FROM users WHERE patient_id=?",
                (patient_id,)
            )
        except sqlite3.OperationalError:
            cursor.execute("SELECT username, name, role, patient_id, age, sex FROM users WHERE patient_id=?", (patient_id,))
        user = cursor.fetchone()
        if user:
            user = list(user) + [None] * (11 - len(user))
            user = tuple(user[:11])
        
        medical_info = None
        if user:
            try:
                cursor.execute(
                    """SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications,
                       height, weight, sex, height_feet, height_inches, waist_cm, hip_cm, body_fat_pct, lean_mass_kg,
                       weight_units, height_units, diabetes_type, chronic_conditions, weekly_food_budget, activity_level
                       FROM patient_medical_info WHERE username=?""",
                    (user[0].lower(),)
                )
                med_data = cursor.fetchone()
                if med_data:
                    med_data = list(med_data) + [None] * (20 - len(med_data))
                    medical_info = {
                        "past_medical_history": med_data[0] or "",
                        "patient_goals": med_data[1] or "",
                        "food_allergies": med_data[2] or "",
                        "physical_activity": med_data[3] or "",
                        "current_medications": med_data[4] or "",
                        "height": med_data[5] or "",
                        "weight": med_data[6] or "",
                        "sex": med_data[7] or (user[5] if len(user) > 5 and user[5] else ""),
                        "height_feet": med_data[8],
                        "height_inches": med_data[9],
                        "waist_cm": med_data[10] or "",
                        "hip_cm": med_data[11] or "",
                        "body_fat_pct": med_data[12] or "",
                        "lean_mass_kg": med_data[13] or "",
                        "weight_units": med_data[14] or "",
                        "height_units": med_data[15] or "",
                        "diabetes_type": med_data[16] or "",
                        "chronic_conditions": med_data[17] or "",
                        "weekly_food_budget": med_data[18] or "",
                        "activity_level": med_data[19] or "",
                    }
                else:
                    medical_info = _empty_medical_info(user[5] if len(user) > 5 and user[5] else "")
            except Exception as e:
                print(f"Error loading medical info: {e}")
                medical_info = _empty_medical_info(user[5] if len(user) > 5 and user[5] else "")
        
        conn.close()
        
        if user:
            return jsonify({
                "username": user[0],
                "name": user[1],
                "role": user[2],
                "patient_id": user[3] or "",
                "age": user[4] if user[4] else None,
                "sex": medical_info["sex"] if medical_info else (user[5] if len(user) > 5 and user[5] else ""),
                "date_of_birth": user[6] if len(user) > 6 else None,
                "middle_initial": user[7] if len(user) > 7 else None,
                "last_name": user[8] if len(user) > 8 else None,
                "biological_sex": user[9] if len(user) > 9 else (user[5] if len(user) > 5 else None),
                "gender_identity": user[10] if len(user) > 10 else None,
                "medical_info": medical_info
            })
        return jsonify({"error": "Patient not found"}), 404
    except Exception as e:
        print(f"Error in get_user_by_patient_id: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/users/<username>', methods=['PUT'])
def update_user(username):
    """Update user information (name, age, sex, date_of_birth, middle_initial, last_name, biological_sex, gender_identity)."""
    data = request.get_json()
    name = data.get('name', '')
    if not name:
        return jsonify({"error": "Name is required"}), 400
    uname = username.lower()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    updates = ["name=?"]
    values = [name]
    optional = [
        ("age", data.get("age")),
        ("sex", data.get("sex")),
        ("date_of_birth", data.get("date_of_birth")),
        ("middle_initial", data.get("middle_initial")),
        ("last_name", data.get("last_name")),
        ("biological_sex", data.get("biological_sex")),
        ("gender_identity", data.get("gender_identity")),
    ]
    for key, val in optional:
        if val is not None:
            updates.append(f"{key}=?")
            values.append(val)
    values.append(uname)
    try:
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE username=?", values)
    except sqlite3.OperationalError as e:
        conn.close()
        if "no such column" in str(e).lower():
            return jsonify({"error": "Server schema outdated; restart server to run migrations"}), 500
        raise
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "User updated successfully"})

@app.route('/api/users/<username>/preferences', methods=['GET'])
def get_preferences(username):
    """Get user preferences"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT likes, dislikes FROM preferences WHERE username=?",
        (username.lower(),)
    )
    prefs = cursor.fetchone()
    conn.close()
    
    if prefs:
        return jsonify({
            "likes": prefs[0] or "",
            "dislikes": prefs[1] or ""
        })
    else:
        return jsonify({"likes": "", "dislikes": ""})


@app.route('/api/users/by-patient-id/<patient_id>/preferences', methods=['GET'])
def get_preferences_by_patient_id(patient_id):
    """Get preferences by patient_id (tries resolved username, then username=patient_id)."""
    pid = str(patient_id).strip()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE patient_id=?", (pid,))
    row = cursor.fetchone()
    username = row[0] if row else None
    out = {"likes": "", "dislikes": ""}
    for uname in ([username] if username else []) + ([pid] if pid else []):
        if not uname:
            continue
        cursor.execute("SELECT likes, dislikes FROM preferences WHERE username=?", (uname.lower(),))
        prefs = cursor.fetchone()
        if not prefs:
            cursor.execute("SELECT likes, dislikes FROM preferences WHERE username=?", (uname,))
            prefs = cursor.fetchone()
        if prefs and (prefs[0] or prefs[1]):
            out = {"likes": prefs[0] or "", "dislikes": prefs[1] or ""}
            break
    conn.close()
    return jsonify(out)

@app.route('/api/users/<username>/preferences', methods=['POST'])
def update_preferences(username):
    """Update user preferences"""
    data = request.get_json()
    likes = data.get('likes', '')
    dislikes = data.get('dislikes', '')
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO preferences (username, likes, dislikes) 
           VALUES (?, ?, ?) 
           ON CONFLICT(username) DO UPDATE SET likes=excluded.likes, dislikes=excluded.dislikes""",
        (username.lower(), likes, dislikes)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Preferences updated successfully"})

@app.route('/api/users/<username>/notes', methods=['GET'])
def get_notes(username):
    """Get doctor notes for a user (case-insensitive username match)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    uname_lower = username.lower() if username else ""
    cursor.execute(
        "SELECT note, created_at FROM notes WHERE LOWER(username)=? ORDER BY created_at DESC",
        (uname_lower,)
    )
    notes = cursor.fetchall()
    cursor.execute("SELECT username FROM notes")
    all_usernames = [r[0] for r in cursor.fetchall()]
    conn.close()
    print(f"[get_notes] username={username!r} LOWER={uname_lower!r} -> {len(notes)} notes (all notes usernames: {all_usernames})")
    return jsonify([
        {"note": note[0], "created_at": note[1]}
        for note in notes
    ])


@app.route('/api/users/by-patient-id/<patient_id>/notes', methods=['GET'])
def get_notes_by_patient_id(patient_id):
    """Get doctor notes for a user by patient_id. Returns notes under username, or under patient_id if stored that way."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    pid = str(patient_id).strip()
    cursor.execute("SELECT username FROM users WHERE patient_id=?", (pid,))
    row = cursor.fetchone()
    username = row[0] if row else None
    uname_lower = (username or "").lower()
    cursor.execute(
        "SELECT note, created_at FROM notes WHERE LOWER(username)=? ORDER BY created_at DESC",
        (uname_lower,)
    )
    notes = cursor.fetchall()
    # If no notes under username, also check under patient_id (doctor may have stored notes that way)
    if len(notes) == 0 and pid:
        cursor.execute(
            "SELECT note, created_at FROM notes WHERE username=? ORDER BY created_at DESC",
            (pid,)
        )
        notes = cursor.fetchall()
    conn.close()
    print(f"[notes by-patient-id] patient_id={pid!r} -> username={username!r} -> {len(notes)} notes")
    return jsonify([
        {"note": note[0], "created_at": note[1]}
        for note in notes
    ])

def _notes_summary_for_username(cursor, username):
    """Return notes summary dict for a username (case-insensitive). cursor must be open; caller closes conn."""
    uname_lower = (username or "").lower()
    cursor.execute(
        "SELECT note, created_at FROM notes WHERE LOWER(username)=? ORDER BY created_at DESC",
        (uname_lower,)
    )
    notes = cursor.fetchall()
    if not notes:
        return {
            "summary": "No doctor notes available yet.",
            "total_notes": 0,
            "latest_note": None,
            "latest_date": None
        }
    def fmt_ts(ms):
        if ms is None:
            return ""
        try:
            return datetime.fromtimestamp(ms / 1000.0).strftime("%d %b %Y, %H:%M")
        except (ValueError, OSError):
            return str(ms)
    latest_note = notes[0][0] if notes else None
    latest_ts = notes[0][1] if notes else None
    parts = []
    parts.append(f"Most recent note ({fmt_ts(latest_ts)}):")
    parts.append("")
    parts.append(latest_note.strip())
    if len(notes) > 1:
        parts.append("")
        parts.append("Earlier notes:")
        for note_text, created_at in notes[1:]:
            parts.append("")
            parts.append(f"• {fmt_ts(created_at)}")
            parts.append("  " + note_text.strip().replace("\n", "\n  "))
    summary = "\n".join(parts)
    return {
        "summary": summary,
        "total_notes": len(notes),
        "last_updated": latest_ts,
        "latest_note": latest_note.strip() if latest_note else None,
        "latest_date": fmt_ts(latest_ts)
    }


@app.route('/api/users/<username>/notes/summary', methods=['GET'])
def get_notes_summary(username):
    """Get a readable summary of all doctor notes for a user (most recent first)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    result = _notes_summary_for_username(cursor, username)
    conn.close()
    print(f"[notes/summary] username={username!r} -> {result['total_notes']} notes")
    return jsonify(result)


@app.route('/api/users/by-patient-id/<patient_id>/notes/summary', methods=['GET'])
def get_notes_summary_by_patient_id(patient_id):
    """Get notes summary by patient ID (so patient always gets their notes)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE patient_id=?", (str(patient_id).strip(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        print(f"[notes/summary by-patient-id] patient_id={patient_id!r} -> no user found")
        return jsonify({
            "summary": "No doctor notes available yet.",
            "total_notes": 0,
            "latest_note": None,
            "latest_date": None
        })
    username = row[0]
    result = _notes_summary_for_username(cursor, username)
    conn.close()
    print(f"[notes/summary by-patient-id] patient_id={patient_id!r} -> username={username!r} -> {result['total_notes']} notes")
    return jsonify(result)

@app.route('/api/users/<username>/notes', methods=['POST'])
def add_note(username):
    """Add a doctor note for a user (store username in lowercase)."""
    data = request.get_json()
    note = data.get('note', '')
    
    if not note:
        return jsonify({"error": "Note is required"}), 400
    
    created_at = int(datetime.now().timestamp() * 1000)  # Milliseconds since epoch
    uname_lower = (username or "").strip().lower()
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notes (username, note, created_at) VALUES (?, ?, ?)",
        (uname_lower, note, created_at)
    )
    conn.commit()
    conn.close()
    print(f"[add_note] username from URL={username!r} -> stored as {uname_lower!r}")
    return jsonify({"message": "Note added successfully"}), 201

@app.route('/api/users/<username>/medical-info', methods=['GET'])
def get_medical_info(username):
    """Get patient medical information (includes new biometric/conditions fields)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications,
               height, weight, sex, height_feet, height_inches, waist_cm, hip_cm, body_fat_pct, lean_mass_kg,
               weight_units, height_units, diabetes_type, chronic_conditions, weekly_food_budget, activity_level
               FROM patient_medical_info WHERE username=?""",
            (username.lower(),)
        )
        med_data = cursor.fetchone()
    except sqlite3.OperationalError:
        med_data = None
    conn.close()
    if med_data:
        med_data = list(med_data) + [None] * (20 - len(med_data))
        return jsonify({
            "past_medical_history": med_data[0] or "",
            "patient_goals": med_data[1] or "",
            "food_allergies": med_data[2] or "",
            "physical_activity": med_data[3] or "",
            "current_medications": med_data[4] or "",
            "height": med_data[5] or "",
            "weight": med_data[6] or "",
            "sex": med_data[7] or "",
            "height_feet": med_data[8],
            "height_inches": med_data[9],
            "waist_cm": med_data[10] or "",
            "hip_cm": med_data[11] or "",
            "body_fat_pct": med_data[12] or "",
            "lean_mass_kg": med_data[13] or "",
            "weight_units": med_data[14] or "",
            "height_units": med_data[15] or "",
            "diabetes_type": med_data[16] or "",
            "chronic_conditions": med_data[17] or "",
            "weekly_food_budget": med_data[18] or "",
            "activity_level": med_data[19] or "",
        })
    return jsonify(_empty_medical_info(""))


@app.route('/api/users/by-patient-id/<patient_id>/medical-info', methods=['GET'])
def get_medical_info_by_patient_id(patient_id):
    """Get medical info by patient_id (tries resolved username, then username=patient_id)."""
    pid = str(patient_id).strip()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE patient_id=?", (pid,))
    row = cursor.fetchone()
    username = row[0] if row else None
    for uname in ([username] if username else []) + ([pid] if pid else []):
        if not uname:
            continue
        try:
            cursor.execute(
                """SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications,
                   height, weight, sex, height_feet, height_inches, waist_cm, hip_cm, body_fat_pct, lean_mass_kg,
                   weight_units, height_units, diabetes_type, chronic_conditions, weekly_food_budget, activity_level
                   FROM patient_medical_info WHERE username=?""",
                (uname.lower(),)
            )
            med = cursor.fetchone()
            if not med:
                cursor.execute(
                    """SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications,
                       height, weight, sex, height_feet, height_inches, waist_cm, hip_cm, body_fat_pct, lean_mass_kg,
                       weight_units, height_units, diabetes_type, chronic_conditions, weekly_food_budget, activity_level
                       FROM patient_medical_info WHERE username=?""",
                    (uname,)
                )
                med = cursor.fetchone()
        except sqlite3.OperationalError:
            med = None
        if med and any(med):
            med = list(med) + [None] * (20 - len(med))
            conn.close()
            return jsonify({
                "past_medical_history": med[0] or "",
                "patient_goals": med[1] or "",
                "food_allergies": med[2] or "",
                "physical_activity": med[3] or "",
                "current_medications": med[4] or "",
                "height": med[5] or "",
                "weight": med[6] or "",
                "sex": med[7] or "",
                "height_feet": med[8],
                "height_inches": med[9],
                "waist_cm": med[10] or "",
                "hip_cm": med[11] or "",
                "body_fat_pct": med[12] or "",
                "lean_mass_kg": med[13] or "",
                "weight_units": med[14] or "",
                "height_units": med[15] or "",
                "diabetes_type": med[16] or "",
                "chronic_conditions": med[17] or "",
                "weekly_food_budget": med[18] or "",
                "activity_level": med[19] or "",
            })
    conn.close()
    return jsonify(_empty_medical_info(""))

@app.route('/api/users/<username>/medical-info', methods=['POST'])
def update_medical_info(username):
    """Update patient medical information (includes new biometric/conditions fields)."""
    data = request.get_json()
    uname = username.lower()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO patient_medical_info (
            username, past_medical_history, patient_goals, food_allergies,
            physical_activity, current_medications, height, weight, sex,
            height_feet, height_inches, waist_cm, hip_cm, body_fat_pct, lean_mass_kg,
            weight_units, height_units, diabetes_type, chronic_conditions, weekly_food_budget, activity_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            past_medical_history=excluded.past_medical_history,
            patient_goals=excluded.patient_goals,
            food_allergies=excluded.food_allergies,
            physical_activity=excluded.physical_activity,
            current_medications=excluded.current_medications,
            height=excluded.height,
            weight=excluded.weight,
            sex=excluded.sex,
            height_feet=excluded.height_feet,
            height_inches=excluded.height_inches,
            waist_cm=excluded.waist_cm,
            hip_cm=excluded.hip_cm,
            body_fat_pct=excluded.body_fat_pct,
            lean_mass_kg=excluded.lean_mass_kg,
            weight_units=excluded.weight_units,
            height_units=excluded.height_units,
            diabetes_type=excluded.diabetes_type,
            chronic_conditions=excluded.chronic_conditions,
            weekly_food_budget=excluded.weekly_food_budget,
            activity_level=excluded.activity_level""",
        (
            uname,
            data.get('past_medical_history', ''),
            data.get('patient_goals', ''),
            data.get('food_allergies', ''),
            data.get('physical_activity', ''),
            data.get('current_medications', ''),
            data.get('height', ''),
            data.get('weight', ''),
            data.get('sex', ''),
            data.get('height_feet'),
            data.get('height_inches'),
            data.get('waist_cm', ''),
            data.get('hip_cm', ''),
            data.get('body_fat_pct', ''),
            data.get('lean_mass_kg', ''),
            data.get('weight_units', ''),
            data.get('height_units', ''),
            data.get('diabetes_type', ''),
            data.get('chronic_conditions', ''),
            data.get('weekly_food_budget', ''),
            data.get('activity_level', ''),
        )
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Medical information updated successfully"})

@app.route('/api/ai/advice', methods=['POST'])
def get_ai_advice():
    """Get AI advice using OpenAI with conversation memory"""
    if not OPENAI_AVAILABLE:
        return jsonify({"error": "OpenAI not configured. Please install openai package and set OPENAI_API_KEY environment variable."}), 503
    
    data = request.get_json()
    question = data.get('question', '')
    user_name = data.get('user_name', 'User')
    likes = data.get('likes', '')
    dislikes = data.get('dislikes', '')
    notes = data.get('notes', [])
    medical_info = data.get('medical_info', {}) or {}
    conversation_history = data.get('conversation_history', [])
    image = data.get('image')  # optional: data URL (base64) for current message
    role = data.get('role', '')  # 'doctor' = doctor assistant mode
    patient_context = data.get('patient_context', '')  # optional summary when doctor has patient loaded
    
    if not question and not image:
        return jsonify({"error": "Question or image is required"}), 400
    question = question or "What do you see in this image?"
    
    # Get OpenAI API key from environment variable
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return jsonify({"error": "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."}), 503
    
    try:
        # Build context from notes (only include in system message if first message)
        notes_context = ""
        if notes and len(notes) > 0 and len(conversation_history) == 0:
            recent_notes = notes[:3]  # Use most recent 3 notes
            notes_context = "\n".join([f"- {note.get('note', '')}" for note in recent_notes])
        
        # Build doctor-recorded information section (non-empty fields only)
        med = medical_info
        med_parts = []
        if med.get('height'):
            med_parts.append(f"- Height: {med.get('height', '')}")
        elif med.get('height_feet') is not None or med.get('height_inches') is not None:
            ft = med.get('height_feet')
            inch = med.get('height_inches')
            ht = " ".join([x for x in [f"{ft} ft" if ft not in (None, "") else None, f"{inch} in" if inch not in (None, "") else None] if x])
            if ht:
                med_parts.append(f"- Height: {ht}")
        if med.get('weight'):
            med_parts.append(f"- Weight: {med.get('weight', '')}")
        if med.get('past_medical_history'):
            med_parts.append(f"- Past medical history: {med.get('past_medical_history', '')}")
        if med.get('patient_goals'):
            med_parts.append(f"- Patient goals: {med.get('patient_goals', '')}")
        if med.get('food_allergies'):
            med_parts.append(f"- Food allergies: {med.get('food_allergies', '')}")
        if med.get('physical_activity'):
            med_parts.append(f"- Physical activity: {med.get('physical_activity', '')}")
        if med.get('current_medications'):
            med_parts.append(f"- Current medications: {med.get('current_medications', '')}")
        if med.get('diabetes_type'):
            med_parts.append(f"- Diabetes type: {med.get('diabetes_type', '')}")
        if med.get('chronic_conditions'):
            med_parts.append(f"- Chronic conditions: {med.get('chronic_conditions', '')}")
        if med.get('activity_level'):
            med_parts.append(f"- Activity level: {med.get('activity_level', '')}")
        medical_context = "\n".join(med_parts) if med_parts else "None recorded."
        
        # Create system prompt (only on first message)
        messages = []
        if len(conversation_history) == 0:
            if role == 'doctor':
                system_prompt = """You are an AI assistant helping a doctor in their wellbeing practice. Be professional, concise, and accurate. You can answer questions about nutrition, patient care, general health, and wellbeing. If the doctor provides context about a loaded patient, use it to give relevant advice. Do not make up patient data."""
                if patient_context:
                    system_prompt += f"\n\nCurrent patient context (if the question is about this patient):\n{patient_context}"
                messages.append({"role": "system", "content": system_prompt})
            else:
                system_prompt = f"""You are a helpful Wellbeing Companion for {user_name}. 
You provide personalized advice about health, recipes, and wellbeing.

User Preferences:
- Likes: {likes if likes else 'Not specified'}
- Dislikes: {dislikes if dislikes else 'Not specified'}

Important: When suggesting recipes, meals, or any food recommendations, you MUST respect the user's dislikes. Never recommend or suggest any food, ingredient, or meal that appears in their dislikes list. Use their likes when possible to suggest foods they enjoy.

Doctor-recorded information (use this to personalize advice and avoid conflicting with care plans):
{medical_context}

Recent Doctor Notes:
{notes_context if notes_context else 'No notes available'}

Provide helpful, personalized advice that takes into account the user's preferences and medical context. Be friendly, supportive, and informative. Remember previous parts of the conversation to maintain context."""
                messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history (user messages may include image - use content array for vision)
        for msg in conversation_history:
            if msg.get('role') not in ['user', 'assistant']:
                continue
            role = msg['role']
            content = msg.get('content', '')
            img = msg.get('image')
            if role == 'user' and img and str(img).startswith('data:image'):
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": content or "(Image attached)"},
                        {"type": "image_url", "image_url": {"url": img}}
                    ]
                })
            else:
                messages.append({"role": role, "content": content or ""})
        
        # Current user message (with optional image)
        if image and str(image).startswith('data:image'):
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image}}
                ]
            })
        else:
            messages.append({"role": "user", "content": question})
        
        # Use vision model when any message has an image (current or in history)
        has_image = image and str(image).startswith('data:image')
        if not has_image:
            for msg in conversation_history:
                if msg.get('role') == 'user' and msg.get('image') and str(msg.get('image', '')).startswith('data:image'):
                    has_image = True
                    break
        model = "gpt-4o-mini" if has_image else "gpt-3.5-turbo"
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        response_text = completion.choices[0].message.content
        return jsonify({"response": response_text})
        
    except Exception as e:
        print(f"OpenAI API error: {str(e)}")
        return jsonify({"error": f"AI service error: {str(e)}"}), 500


@app.route('/api/ai/nutrition-plan', methods=['POST'])
def generate_nutrition_plan():
    """Generate a personalized nutrition plan for a patient using their recorded data."""
    if not OPENAI_AVAILABLE:
        return jsonify({"error": "OpenAI not configured."}), 503
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return jsonify({"error": "OpenAI API key not configured."}), 503
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    patient_id = (data.get('patient_id') or '').strip()
    if not username and not patient_id:
        return jsonify({"error": "Provide username or patient_id"}), 400
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        if patient_id and not username:
            cursor.execute("SELECT username FROM users WHERE patient_id=?", (patient_id,))
            row = cursor.fetchone()
            username = (row[0] or '').strip() if row else ''
        if not username:
            conn.close()
            return jsonify({"error": "Patient not found"}), 404
        uname_lower = username.lower()
        cursor.execute(
            "SELECT name, age, sex FROM users WHERE username=?", (uname_lower,)
        )
        user_row = cursor.fetchone()
        user_name = user_row[0] if user_row else username
        user_age = user_row[1] if user_row and len(user_row) > 1 else None
        user_sex = user_row[2] if user_row and len(user_row) > 2 else ""
        cursor.execute(
            "SELECT likes, dislikes FROM preferences WHERE username=?", (uname_lower,)
        )
        prefs_row = cursor.fetchone()
        likes = (prefs_row[0] or "") if prefs_row else ""
        dislikes = (prefs_row[1] or "") if prefs_row and len(prefs_row) > 1 else ""
        cursor.execute(
            "SELECT note, created_at FROM notes WHERE LOWER(username)=? ORDER BY created_at DESC LIMIT 5",
            (uname_lower,)
        )
        notes_rows = cursor.fetchall()
        notes_txt = "\n".join([n[0] or "" for n in notes_rows]) if notes_rows else ""
        try:
            cursor.execute(
                """SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications,
                   height, weight, height_feet, height_inches, diabetes_type, chronic_conditions, activity_level
                   FROM patient_medical_info WHERE username=?""",
                (uname_lower,)
            )
            med = cursor.fetchone()
        except sqlite3.OperationalError:
            med = None
        conn.close()
        med = list(med) + [None] * (12 - len(med)) if med else [None] * 12
        ctx_parts = [
            f"Patient: {user_name}",
            f"Age: {user_age or 'Not specified'}",
            f"Sex: {user_sex or 'Not specified'}",
            f"Likes: {likes or 'None'}",
            f"Dislikes: {dislikes or 'None'}",
        ]
        if med[0]: ctx_parts.append(f"Past medical history: {med[0]}")
        if med[1]: ctx_parts.append(f"Patient goals: {med[1]}")
        if med[2]: ctx_parts.append(f"Food allergies: {med[2]}")
        if med[3]: ctx_parts.append(f"Physical activity: {med[3]}")
        if med[4]: ctx_parts.append(f"Current medications: {med[4]}")
        if med[5] or med[7] is not None or med[8] is not None:
            ht = med[5] or (f"{med[7] or ''} ft {med[8] or ''} in".strip())
            ctx_parts.append(f"Height: {ht}")
        if med[6]: ctx_parts.append(f"Weight: {med[6]}")
        if med[9]: ctx_parts.append(f"Diabetes type: {med[9]}")
        if med[10]: ctx_parts.append(f"Chronic conditions: {med[10]}")
        if med[11]: ctx_parts.append(f"Activity level: {med[11]}")
        if notes_txt:
            ctx_parts.append("Recent doctor notes:\n" + notes_txt)
        context = "\n".join(ctx_parts)
        prompt = f"""Generate a personalized nutrition plan for this patient. Use ONLY the information below. Return a JSON object with exactly these keys (all strings; for arrays use JSON arrays of strings):

- maintenance_calories: e.g. "2000"
- weight_loss_calories: e.g. "1500"
- carbs_g: e.g. "200"
- protein_g: e.g. "150"
- fats_g: e.g. "65"
- foods_include: array of 3-5 food items to include (prefer the patient's likes; NEVER include any food from their dislikes list)
- foods_avoid: array of 3-5 foods to avoid based ONLY on medical needs (allergies, conditions, diabetes, medications, interactions). Do NOT put the patient's dislikes here—this section is strictly medically relevant (e.g. allergens, foods that worsen conditions, or that interact with medications).
- day1_breakfast, day1_lunch, day1_dinner: meal descriptions (must NOT contain any foods from the patient's dislikes)
- day2_breakfast, day2_lunch, day2_dinner: meal descriptions (must NOT contain any foods from the patient's dislikes)
- day3_breakfast, day3_lunch, day3_dinner: meal descriptions (must NOT contain any foods from the patient's dislikes)
- grocery_produce, grocery_grains, grocery_proteins, grocery_fats_extras: arrays of 5 items each (must NOT include any foods from the patient's dislikes)
- smart_goal: one short SMART goal sentence
- references: optional short note or "—"

Patient context:
{context}

Return only valid JSON, no other text. Use the patient's age, sex, weight, goals, allergies, and activity to set realistic numbers. CRITICAL: Do not suggest or include ANY food from the patient's "Dislikes" list anywhere in the plan—not in meals, foods_include, or grocery lists. Use their likes when suggesting foods they might enjoy. foods_avoid = medically relevant only (allergies, conditions, drug interactions)."""

        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        raw = completion.choices[0].message.content or "{}"
        try:
            plan_data = json.loads(raw)
        except Exception:
            plan_data = {"_raw": raw}
        return jsonify({"plan": plan_data})
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"Nutrition plan error: {e}")
        return jsonify({"error": str(e)}), 500


# Serve frontend (for all-in-one deployment)
@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if filename in ALLOWED_STATIC:
        return send_from_directory(BASE_DIR, filename)
    return '', 404


# Initialize database when app is loaded (needed when running under gunicorn on Render)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print("=" * 50)
    print("Wellbeing Companion Backend Server")
    print("=" * 50)
    print(f"Database: {DB_NAME}")
    print(f"Server starting on http://0.0.0.0:{port}")
    print(f"API Base URL: http://0.0.0.0:{port}/api")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=debug)


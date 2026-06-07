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
import shutil
import sys
import uuid
import string
import random
import secrets
import unicodedata
import re
import hmac
import hashlib
import urllib.request
import urllib.error
import smtplib
import ssl
import threading
from email.message import EmailMessage
from datetime import datetime


def _norm(s):
    """Normalize string for login/register: strip and NFKC so different devices match."""
    if s is None:
        return ''
    return unicodedata.normalize('NFKC', str(s).strip())

# OpenAI integration (optional - install with: pip install openai)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI not installed. AI features will not work.")
    print("Install with: pip install openai")

try:
    from open_clinical_sources import (
        gather_open_source_clinical_block,
        gather_open_source_clinical_bundle,
        build_repository_pubmed_block,
        pubmed_references_for_pmids,
        rank_pmids_for_question,
        filter_pubmed_references_cited_in_response,
    )
except ImportError:
    gather_open_source_clinical_block = None
    gather_open_source_clinical_bundle = None
    build_repository_pubmed_block = None
    pubmed_references_for_pmids = None
    rank_pmids_for_question = None
    filter_pubmed_references_cited_in_response = None

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Directory containing this script (for static files and legacy SQLite migration).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_sqlite_database_path():
    """SQLite file path: explicit env wins; on Render with /data mounted, default to the persistent disk."""
    explicit = (os.environ.get('SQLITE_DATABASE_PATH') or os.environ.get('SQLITE_PATH') or '').strip()
    if explicit:
        return explicit
    if os.environ.get('RENDER') and os.path.isdir('/data'):
        return '/data/wellbeing.db'
    return 'wellbeing.db'


# Database: SQLite by default, or PostgreSQL when DATABASE_URL is set (persists across redeploys on the host).
# On Render/Fly/similar, default SQLite lives on an ephemeral disk — set DATABASE_URL (Postgres) or
# SQLITE_DATABASE_PATH to a file on a mounted persistent disk (e.g. /data/wellbeing.db).
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)  # psycopg2 expects postgresql://
USE_PG = bool(DATABASE_URL and 'postgresql' in DATABASE_URL.lower())
SQLITE_DATABASE_PATH = _resolve_sqlite_database_path()

def get_conn():
    if USE_PG:
        try:
            import psycopg2
            return psycopg2.connect(DATABASE_URL)
        except ImportError:
            pass
    return sqlite3.connect(SQLITE_DATABASE_PATH)


def _sqlite_user_count(path):
    try:
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cur.fetchone():
                return 0
            cur.execute("SELECT COUNT(*) FROM users")
            return int(cur.fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return 0


def _sqlite_clone_via_backup(src_path, dst_path):
    """Copy a SQLite database file using the backup API (works with WAL)."""
    dst_abs = os.path.abspath(dst_path)
    parent = os.path.dirname(dst_abs)
    if parent:
        os.makedirs(parent, exist_ok=True)
    for suffix in ('', '-wal', '-shm'):
        p = dst_abs + suffix if suffix else dst_abs
        if os.path.isfile(p):
            os.remove(p)
    src_conn = sqlite3.connect(src_path)
    try:
        dst_conn = sqlite3.connect(dst_abs)
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _maybe_migrate_legacy_sqlite():
    """
    One-time style migration: if wellbeing.db next to server.py has more account data than the
    configured DB file, copy it onto the target path (e.g. /data/wellbeing.db after adding a disk).
    """
    if USE_PG:
        return
    target = os.path.abspath(SQLITE_DATABASE_PATH)
    legacy = os.path.abspath(os.path.join(BASE_DIR, 'wellbeing.db'))
    if legacy == target or not os.path.isfile(legacy):
        return
    legacy_users = _sqlite_user_count(legacy)
    if legacy_users == 0:
        return
    if not os.path.isfile(target):
        _sqlite_clone_via_backup(legacy, target)
        print(f"SQLite: migrated {legacy_users} user row(s) from legacy file -> {target}")
        return
    target_users = _sqlite_user_count(target)
    if legacy_users > target_users:
        bak = target + '.bak-before-migrate'
        shutil.copy2(target, bak)
        _sqlite_clone_via_backup(legacy, target)
        print(
            f"SQLite: replaced target ({target_users} user(s)) with legacy ({legacy_users} user(s)); "
            f"previous DB copied to {bak}"
        )


def _run_execute_impl(cursor, sql, params=None):
    if params is None:
        params = ()
    if USE_PG:
        cursor.execute(sql.replace('?', '%s'), params)
    else:
        cursor.execute(sql, params)

def run_execute(cursor, sql, params=None):
    _run_execute_impl(cursor, sql, params)

ALLOWED_STATIC = {
    'index.html',
    'admin.html',
    'styles.css',
    'app.js',
    'admin.js',
    'admin-ai-log.js',
    'admin-setup.js',
    'api-service.js',
    'logo.png',
    'pwa-icon-192.png',
    'pwa-icon-512.png',
    'favicon.ico',
}

# Unique ID for this server instance (different containers = different IDs; compare laptop vs tablet)
INSTANCE_ID = os.environ.get('RENDER_INSTANCE_ID') or str(uuid.uuid4())[:8]

def generate_patient_id():
    """Generate a unique numerical patient ID"""
    # Generate a random 6-digit number
    while True:
        # Generate number between 100000 and 999999
        patient_id = random.randint(100000, 999999)
        # Check if it's already taken
        conn = get_conn()
        cursor = conn.cursor()
        run_execute(cursor,"SELECT username FROM users WHERE patient_id=?", (str(patient_id),))
        if not cursor.fetchone():
            conn.close()
            return str(patient_id)
        conn.close()

def init_db():
    """Initialize the database with required tables (SQLite or PostgreSQL)."""
    if USE_PG:
        init_db_pg()
        return
    _parent = os.path.dirname(os.path.abspath(SQLITE_DATABASE_PATH))
    if _parent:
        os.makedirs(_parent, exist_ok=True)
    conn = get_conn()
    cursor = conn.cursor()
    
    # Users table
    run_execute(cursor, """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            patient_id TEXT UNIQUE,
            age INTEGER
        )
    """)
    
    try:
        run_execute(cursor, "ALTER TABLE users ADD COLUMN patient_id TEXT")
    except (sqlite3.OperationalError, Exception):
        pass
    try:
        run_execute(cursor, "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_patient_id_unique'")
        if not cursor.fetchone():
            run_execute(cursor, "CREATE UNIQUE INDEX IF NOT EXISTS idx_patient_id_unique ON users(patient_id) WHERE patient_id IS NOT NULL")
    except (sqlite3.OperationalError, Exception):
        pass
    try:
        run_execute(cursor, "ALTER TABLE users ADD COLUMN age INTEGER")
    except (sqlite3.OperationalError, Exception):
        pass
    try:
        run_execute(cursor, "ALTER TABLE users ADD COLUMN onboarding_completed INTEGER DEFAULT 1")
    except (sqlite3.OperationalError, Exception):
        pass
    
    run_execute(cursor, "SELECT username, patient_id FROM users WHERE role='Patient'")
    all_patients = cursor.fetchall()
    for (username, existing_id) in all_patients:
        if not existing_id or (str(existing_id or '')).startswith('PAT-'):
            new_id = generate_patient_id()
            run_execute(cursor, "UPDATE users SET patient_id=? WHERE username=?", (new_id, username))
            print(f"Generated Patient ID {new_id} for {username}")
    
    run_execute(cursor, """
        CREATE TABLE IF NOT EXISTS preferences (
            username TEXT PRIMARY KEY,
            likes TEXT,
            dislikes TEXT,
            religion TEXT,
            culture TEXT,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    for col in ("religion", "culture"):
        try:
            run_execute(cursor, f"ALTER TABLE preferences ADD COLUMN {col} TEXT")
        except (sqlite3.OperationalError, Exception):
            pass
    run_execute(cursor, """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    run_execute(cursor, """
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
    try:
        run_execute(cursor, "ALTER TABLE users ADD COLUMN sex TEXT")
    except (sqlite3.OperationalError, Exception):
        pass
    for col, ctype in [
        ("date_of_birth", "TEXT"), ("middle_initial", "TEXT"), ("last_name", "TEXT"),
        ("biological_sex", "TEXT"), ("gender_identity", "TEXT"),
    ]:
        try:
            run_execute(cursor, f"ALTER TABLE users ADD COLUMN {col} {ctype}")
        except (sqlite3.OperationalError, Exception):
            pass
    for col, ctype in [
        ("height_feet", "INTEGER"), ("height_inches", "REAL"), ("waist_cm", "TEXT"),
        ("hip_cm", "TEXT"), ("body_fat_pct", "TEXT"), ("lean_mass_kg", "TEXT"),
        ("weight_units", "TEXT"), ("height_units", "TEXT"), ("diabetes_type", "TEXT"),
        ("chronic_conditions", "TEXT"), ("weekly_food_budget", "TEXT"), ("activity_level", "TEXT"),
    ]:
        try:
            run_execute(cursor, f"ALTER TABLE patient_medical_info ADD COLUMN {col} {ctype}")
        except (sqlite3.OperationalError, Exception):
            pass

    run_execute(cursor, """
        CREATE TABLE IF NOT EXISTS literature_repository (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            patient_username TEXT,
            pmid TEXT NOT NULL,
            curator_note TEXT,
            added_by TEXT,
            created_at INTEGER NOT NULL
        )
    """)
    try:
        run_execute(cursor,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_lit_global_pmid ON literature_repository(pmid) WHERE scope = 'global'")
    except (sqlite3.OperationalError, Exception):
        pass
    try:
        run_execute(cursor,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_lit_patient_pmid ON literature_repository(patient_username, pmid) WHERE scope = 'patient'")
    except (sqlite3.OperationalError, Exception):
        pass
    run_execute(cursor, """
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            source TEXT,
            created_at INTEGER NOT NULL
        )
    """)
    run_execute(cursor, """
        CREATE TABLE IF NOT EXISTS ai_chat_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at INTEGER NOT NULL,
            username TEXT NOT NULL,
            display_name TEXT,
            role TEXT,
            context_username TEXT,
            source TEXT,
            question TEXT NOT NULL,
            response TEXT,
            references_json TEXT,
            model TEXT,
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT,
            had_image INTEGER NOT NULL DEFAULT 0
        )
    """)
    try:
        run_execute(cursor,
            "CREATE INDEX IF NOT EXISTS idx_ai_chat_log_created ON ai_chat_log(created_at DESC)")
    except (sqlite3.OperationalError, Exception):
        pass
    for col, ctype in [("rating", "INTEGER"), ("rated_at", "INTEGER")]:
        try:
            run_execute(cursor, f"ALTER TABLE ai_chat_log ADD COLUMN {col} {ctype}")
        except (sqlite3.OperationalError, Exception):
            pass
    conn.commit()
    conn.close()


def init_db_pg():
    """Create PostgreSQL tables (one shared DB for all devices)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(255) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            role VARCHAR(64) NOT NULL,
            patient_id VARCHAR(32) UNIQUE,
            age INTEGER,
            sex VARCHAR(64),
            date_of_birth TEXT, middle_initial TEXT, last_name TEXT,
            biological_sex TEXT, gender_identity TEXT,
            onboarding_completed INTEGER DEFAULT 0
        )
    """)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed INTEGER DEFAULT 1")
    except Exception:
        pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            username VARCHAR(255) PRIMARY KEY REFERENCES users(username),
            likes TEXT, dislikes TEXT, religion TEXT, culture TEXT
        )
    """)
    for col in ("religion", "culture"):
        try:
            cur.execute(f"ALTER TABLE preferences ADD COLUMN IF NOT EXISTS {col} TEXT")
        except Exception:
            pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL REFERENCES users(username),
            note TEXT NOT NULL,
            created_at BIGINT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patient_medical_info (
            username VARCHAR(255) PRIMARY KEY REFERENCES users(username),
            past_medical_history TEXT, patient_goals TEXT, food_allergies TEXT,
            physical_activity TEXT, current_medications TEXT, height TEXT, weight TEXT, sex TEXT,
            height_feet INTEGER, height_inches REAL, waist_cm TEXT, hip_cm TEXT, body_fat_pct TEXT,
            lean_mass_kg TEXT, weight_units TEXT, height_units TEXT, diabetes_type TEXT,
            chronic_conditions TEXT, weekly_food_budget TEXT, activity_level TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS literature_repository (
            id SERIAL PRIMARY KEY,
            scope VARCHAR(16) NOT NULL,
            patient_username VARCHAR(255) REFERENCES users(username) ON DELETE CASCADE,
            pmid VARCHAR(32) NOT NULL,
            curator_note TEXT,
            added_by VARCHAR(255),
            created_at BIGINT NOT NULL
        )
    """)
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_lit_global_pmid ON literature_repository (pmid) WHERE scope = 'global'"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_lit_patient_pmid ON literature_repository (patient_username, pmid) WHERE scope = 'patient'"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            role VARCHAR(64) NOT NULL,
            message TEXT NOT NULL,
            source VARCHAR(32),
            created_at BIGINT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ai_chat_log (
            id SERIAL PRIMARY KEY,
            created_at BIGINT NOT NULL,
            username VARCHAR(255) NOT NULL,
            display_name VARCHAR(255),
            role VARCHAR(64),
            context_username VARCHAR(255),
            source VARCHAR(32),
            question TEXT NOT NULL,
            response TEXT,
            references_json TEXT,
            model VARCHAR(128),
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT,
            had_image INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_chat_log_created ON ai_chat_log (created_at DESC)"
    )
    for col, ctype in [("rating", "INTEGER"), ("rated_at", "BIGINT")]:
        try:
            cur.execute(f"ALTER TABLE ai_chat_log ADD COLUMN IF NOT EXISTS {col} {ctype}")
        except Exception:
            pass
    conn.commit()
    conn.close()
    print("PostgreSQL tables initialized (shared DB for all devices)")

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


def _sqlite_likely_ephemeral_host():
    """True if we guess SQLite data may be wiped on redeploy (e.g. Render without a persistent disk)."""
    if USE_PG:
        return False
    if os.environ.get('SQLITE_PERSISTENT', '').strip().lower() in ('1', 'true', 'yes'):
        return False
    path = os.path.abspath(SQLITE_DATABASE_PATH).replace('\\', '/')
    for prefix in ('/data/', '/var/data/', '/mnt/'):
        if path.startswith(prefix):
            return False
    return bool(os.environ.get('RENDER'))


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint. instance_id: same on laptop & tablet = same server; different = different DB."""
    payload = {
        "status": "ok",
        "instance_id": INSTANCE_ID,
        "database": "postgresql" if USE_PG else "sqlite",
        "user_data_persists": USE_PG or not _sqlite_likely_ephemeral_host(),
        "ephemeral_data_warning": _sqlite_likely_ephemeral_host(),
    }
    if not USE_PG:
        payload["sqlite_path"] = os.path.abspath(SQLITE_DATABASE_PATH)
    return jsonify(payload)


def _parse_feedback_admin_usernames():
    raw = os.environ.get("FEEDBACK_ADMIN_USERNAMES", "") or ""
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def _verify_user_credentials(username, password):
    """Return dict with username, name, role if password matches; else None."""
    uname = _norm(username or "").lower()
    pwd = _norm(password or "")
    if not uname or not pwd:
        return None
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(
        cursor,
        "SELECT username, password, name, role FROM users WHERE username=?",
        (uname,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or _norm((row[1] or "")) != pwd:
        return None
    return {"username": row[0], "name": row[2], "role": row[3]}


def _lookup_feedback_submitter(username):
    """Load user by username (no password) for in-app feedback from logged-in clients."""
    uname = _norm(username or "").lower()
    if not uname:
        return None
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(
        cursor,
        "SELECT username, name, role FROM users WHERE username=?",
        (uname,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"username": row[0], "name": row[1], "role": row[2]}


_FEEDBACK_EPHEMERAL_SIGNING_KEY = None


def _feedback_signing_key_bytes():
    """HMAC key for feedback session tokens. Set FEEDBACK_AUTH_SECRET on the host for stable multi-worker deploys."""
    global _FEEDBACK_EPHEMERAL_SIGNING_KEY
    raw = (os.environ.get("FEEDBACK_AUTH_SECRET") or "").strip()
    if raw:
        return raw.encode("utf-8")
    if _FEEDBACK_EPHEMERAL_SIGNING_KEY is None:
        _FEEDBACK_EPHEMERAL_SIGNING_KEY = secrets.token_bytes(32)
        print(
            "WARNING: FEEDBACK_AUTH_SECRET is not set. Feedback tokens reset on server restart; "
            "set FEEDBACK_AUTH_SECRET in production (e.g. Render environment)."
        )
    return _FEEDBACK_EPHEMERAL_SIGNING_KEY


def _make_feedback_token(username):
    """Issued only after a successful password login; proves the client recently authenticated."""
    uname = _norm(username or "").lower()
    if not uname:
        return None
    exp = int(datetime.now().timestamp()) + (90 * 24 * 3600)
    msg = f"{uname}|{exp}".encode("utf-8")
    sig = hmac.new(_feedback_signing_key_bytes(), msg, hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def _verify_feedback_token(username, token):
    if not token or not username:
        return False
    uname = _norm(username).lower()
    try:
        exp_s, sig = str(token).strip().split(".", 1)
        exp = int(exp_s)
        if exp < int(datetime.now().timestamp()):
            return False
        msg = f"{uname}|{exp}".encode("utf-8")
        expected = hmac.new(_feedback_signing_key_bytes(), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


def _notify_feedback_webhook(username, role, message, source, ts_ms):
    """Optional Slack/Zapier/etc.: set FEEDBACK_NOTIFY_WEBHOOK to a URL that accepts JSON POST."""
    url = (os.environ.get("FEEDBACK_NOTIFY_WEBHOOK") or "").strip()
    if not url:
        return
    snippet = (message or "").replace("\r", " ").strip()
    if len(snippet) > 3500:
        snippet = snippet[:3497] + "..."
    summary = (
        f"[Wellbeing Companion] Feedback\nUser: {username} ({role})\nSource: {source}\nTime: {ts_ms}\n\n{snippet}"
    )
    # Zapier/Gmail: avoid picking a wrong "Message" field — use feedback_body, wellbeing_feedback_text, or text.
    payload = {
        "text": summary,
        "username": username,
        "role": role,
        "source": source,
        "message": message,
        "feedback_body": message,
        "wellbeing_feedback_text": message,
        "feedback_user_text": message,
        "created_at": ts_ms,
    }
    # Discord incoming webhooks expect "content" (or embeds); "text" alone is ignored.
    if "discord.com/api/webhooks" in url.lower() or "discordapp.com/api/webhooks" in url.lower():
        payload["content"] = summary[:1990]

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        timeout = float((os.environ.get("FEEDBACK_NOTIFY_WEBHOOK_TIMEOUT_SEC") or "25").strip())
        if timeout < 5 or timeout > 120:
            timeout = 25.0
    except ValueError:
        timeout = 25.0
    try:
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "WellbeingCompanion/1.0 (+feedback-webhook)",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1024)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read()[:800].decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        print(
            f"FEEDBACK_NOTIFY_WEBHOOK HTTP {e.code} for {url[:80]}...: {detail or e.reason}"
        )
    except Exception as ex:
        print(f"FEEDBACK_NOTIFY_WEBHOOK request failed: {ex}")


def _feedback_smtp_no_auth():
    return (os.environ.get("FEEDBACK_SMTP_NO_AUTH") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _feedback_email_settings():
    """Read SMTP settings for optional inbox delivery of each feedback (see FEEDBACK_EMAIL_* env vars)."""
    to_raw = (os.environ.get("FEEDBACK_EMAIL_TO") or "").strip()
    host = (os.environ.get("FEEDBACK_SMTP_HOST") or "").strip()
    user = (os.environ.get("FEEDBACK_SMTP_USER") or "").strip()
    password = (
        os.environ.get("FEEDBACK_SMTP_PASSWORD")
        or os.environ.get("FEEDBACK_SMTP_PASS")
        or ""
    ).strip()
    try:
        port = int((os.environ.get("FEEDBACK_SMTP_PORT") or "587").strip())
    except ValueError:
        port = 587
    from_addr = (os.environ.get("FEEDBACK_EMAIL_FROM") or "").strip() or user
    use_ssl = (os.environ.get("FEEDBACK_SMTP_USE_SSL") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if port == 465:
        use_ssl = True
    skip_tls = (os.environ.get("FEEDBACK_SMTP_SKIP_TLS") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    return to_raw, host, user, password, port, from_addr, use_ssl, skip_tls


def _feedback_smtp_configured():
    """True when email-on-feedback is wired (no secrets exposed to clients)."""
    to_raw, host, user, password, _, from_addr, _, _ = _feedback_email_settings()
    if not to_raw or not host or not from_addr:
        return False
    if _feedback_smtp_no_auth():
        return True
    return bool(user and password)


def _smtp_deliver_message(msg):
    """Send a prepared EmailMessage using FEEDBACK_SMTP_* settings."""
    _, host, user, password, port, _, use_ssl, skip_tls = _feedback_email_settings()
    if not host:
        raise RuntimeError("FEEDBACK_SMTP_HOST is not set")
    ctx = ssl.create_default_context()
    no_auth = _feedback_smtp_no_auth()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=45) as smtp:
            if not no_auth:
                smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=45) as smtp:
            smtp.ehlo()
            if not skip_tls:
                smtp.starttls(context=ctx)
                smtp.ehlo()
            if not no_auth:
                smtp.login(user, password)
            smtp.send_message(msg)


def _send_feedback_email_sync(username, role, message, source, ts_ms, feedback_id):
    to_raw, _, _, _, _, from_addr, _, _ = _feedback_email_settings()
    recipients = [x.strip() for x in to_raw.split(",") if x.strip()]
    if not recipients:
        return
    subject = f"[Wellbeing Companion] Feedback from {username} ({role})"
    body = (
        f"New feedback submission\n\n"
        f"User: {username}\n"
        f"Role: {role}\n"
        f"Source: {source}\n"
        f"Submitted at (epoch ms): {ts_ms}\n"
        f"Row id: {feedback_id}\n\n"
        f"Message:\n{message}\n"
    )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.set_content(body, charset="utf-8")
    _smtp_deliver_message(msg)


def _fetch_feedback_rows_chronological(limit=2000):
    """Return feedback rows oldest-first for digest / export."""
    conn = get_conn()
    cursor = conn.cursor()
    rows = []
    try:
        if USE_PG:
            cursor.execute(
                """SELECT id, username, role, message, source, created_at
                   FROM user_feedback ORDER BY created_at ASC LIMIT %s""",
                (limit,),
            )
            for r in cursor.fetchall():
                rows.append(
                    {
                        "id": r[0],
                        "username": r[1],
                        "role": r[2],
                        "message": r[3],
                        "source": r[4] or "",
                        "created_at": r[5],
                    }
                )
        else:
            run_execute(
                cursor,
                """SELECT id, username, role, message, source, created_at
                   FROM user_feedback ORDER BY created_at ASC LIMIT ?""",
                (limit,),
            )
            for r in cursor.fetchall():
                rows.append(
                    {
                        "id": r[0],
                        "username": r[1],
                        "role": r[2],
                        "message": r[3],
                        "source": r[4] or "",
                        "created_at": r[5],
                    }
                )
    finally:
        conn.close()
    return rows


def run_email_feedback_backlog_digest(limit=2000):
    """One email summarizing existing DB rows. Run: python server.py --email-feedback-backlog"""
    if not _feedback_smtp_configured():
        raise RuntimeError(
            "SMTP not configured. Set FEEDBACK_EMAIL_TO, FEEDBACK_EMAIL_FROM, FEEDBACK_SMTP_HOST, "
            "FEEDBACK_SMTP_USER, FEEDBACK_SMTP_PASSWORD (same values as for live feedback email)."
        )
    db_rows = _fetch_feedback_rows_chronological(limit)
    if not db_rows:
        return 0
    lines = [
        f"Wellbeing Companion — stored feedback digest ({len(db_rows)} row(s), oldest first).\n"
        "Each new submission is also emailed individually if SMTP env is set on the server.\n"
    ]
    max_msg = 3500
    for row in db_rows:
        text = row["message"] or ""
        if len(text) > max_msg:
            text = text[: max_msg - 3] + "..."
        lines.append(
            f"---\n"
            f"id={row['id']}  user={row['username']}  role={row['role']}  "
            f"source={row['source']}  created_at_ms={row['created_at']}\n"
            f"{text}\n"
        )
    body = "\n".join(lines)
    subject = f"[Wellbeing Companion] Feedback digest ({len(db_rows)} submissions)"
    to_raw, _, _, _, _, from_addr, _, _ = _feedback_email_settings()
    recipients = [x.strip() for x in to_raw.split(",") if x.strip()]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.set_content(body, charset="utf-8")
    _smtp_deliver_message(msg)
    return len(db_rows)


def _notify_feedback_email(username, role, message, source, ts_ms, feedback_id):
    """Optional inbox copy: set FEEDBACK_EMAIL_TO + FEEDBACK_SMTP_* on the host. Runs in a background thread."""
    if not _feedback_smtp_configured():
        return

    def run():
        try:
            _send_feedback_email_sync(
                username, role, message, source, ts_ms, feedback_id
            )
        except Exception as ex:
            print(f"FEEDBACK email notify failed: {ex}")

    threading.Thread(target=run, daemon=True).start()


def _user_onboarding_completed(username):
    """True if patient finished welcome interview (or not a new patient flow)."""
    uname = _norm(username or "").lower()
    if not uname:
        return True
    try:
        conn = get_conn()
        cursor = conn.cursor()
        run_execute(
            cursor,
            "SELECT onboarding_completed, role FROM users WHERE LOWER(username)=?",
            (uname,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return True
        completed, role = row[0], row[1]
        if _norm(role or "").lower() != "patient":
            return True
        return bool(completed)
    except Exception as ex:
        print(f"onboarding status lookup failed: {ex}")
        return True


def _can_view_feedback_admin(user):
    """Env FEEDBACK_ADMIN_USERNAMES (comma-separated) and/or users with role Admin."""
    if not user:
        return False
    if _norm(user.get("role") or "").lower() == "admin":
        return True
    admins = _parse_feedback_admin_usernames()
    if not admins:
        return False
    return _norm(user.get("username") or "").lower() in admins


def _insert_ai_chat_log(
    *,
    username,
    display_name,
    role,
    context_username,
    source,
    question,
    response=None,
    references=None,
    model=None,
    success=True,
    error_message=None,
    had_image=False,
):
    """Persist one AI Q&A for admin review. Never raises — logging must not break chat."""
    try:
        ts_ms = int(datetime.now().timestamp() * 1000)
        refs_json = None
        if references is not None:
            try:
                refs_json = json.dumps(references, ensure_ascii=False)
            except (TypeError, ValueError):
                refs_json = None
        conn = get_conn()
        cursor = conn.cursor()
        params = (
            ts_ms,
            username or "",
            display_name or "",
            role or "",
            context_username or "",
            source or "",
            question or "",
            response or "",
            refs_json,
            model or "",
            1 if success else 0,
            (error_message or "")[:4000],
            1 if had_image else 0,
        )
        if USE_PG:
            cursor.execute(
                """
                INSERT INTO ai_chat_log (
                    created_at, username, display_name, role, context_username, source,
                    question, response, references_json, model, success, error_message, had_image
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """,
                params,
            )
            row = cursor.fetchone()
            log_id = row[0] if row else None
        else:
            run_execute(
                cursor,
                """
                INSERT INTO ai_chat_log (
                    created_at, username, display_name, role, context_username, source,
                    question, response, references_json, model, success, error_message, had_image
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id
    except Exception as ex:
        print(f"ai_chat_log insert failed: {ex}")
        return None


def _ai_rating_feedback_system_block(username):
    """Recent thumbs-down ratings so the model can adjust on the next reply."""
    uname = _norm(username or "").lower()
    if not uname:
        return None
    try:
        conn = get_conn()
        cursor = conn.cursor()
        run_execute(
            cursor,
            """
            SELECT question, response FROM ai_chat_log
            WHERE LOWER(username)=? AND rating=-1 AND success=1
            ORDER BY rated_at DESC LIMIT 2
            """,
            (uname,),
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return None
        lines = [
            "User feedback: this user recently rated the following AI answers as unhelpful (thumbs down). "
            "Avoid repeating similar mistakes—be clearer, more accurate, and better aligned with their question."
        ]
        for i, (q, r) in enumerate(rows, 1):
            q_short = (q or "")[:200]
            r_short = (r or "")[:300]
            lines.append(f"{i}. Question: {q_short}")
            lines.append(f"   Unhelpful answer excerpt: {r_short}")
        return "\n".join(lines)
    except Exception as ex:
        print(f"ai rating feedback lookup failed: {ex}")
        return None


def _strip_wrapping_quotes_value(val):
    """Strip one layer of surrounding ASCII quotes (common when pasting into env UIs)."""
    s = (str(val or "")).strip()
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        return s[1:-1].strip()
    return s


def _env_strip_outer_quotes(var_name):
    return _strip_wrapping_quotes_value(os.environ.get(var_name))


def _admin_access_secret():
    """If set, feedback admin UI is only served under /console/<secret>/ (not /admin.html)."""
    return _env_strip_outer_quotes("ADMIN_ACCESS_SECRET")


def _admin_bootstrap_key():
    """If set, POST /api/admin/bootstrap can create Admin users when the key matches."""
    return _env_strip_outer_quotes("ADMIN_BOOTSTRAP_KEY")


def _const_time_str_equal(expected, provided, *, casefold=False):
    """Constant-time compare for secrets (any length) via SHA-256 digests."""
    if not expected or provided is None:
        return False
    try:
        ex = str(expected).strip()
        pr = str(provided).strip()
        if casefold:
            ex = ex.casefold()
            pr = pr.casefold()
        a = hashlib.sha256(ex.encode("utf-8")).digest()
        b = hashlib.sha256(pr.encode("utf-8")).digest()
        return hmac.compare_digest(a, b)
    except Exception:
        return False


def _console_secret_ok(secret):
    exp = _admin_access_secret()
    if not exp:
        return False
    return _const_time_str_equal(exp, (secret or "").strip(), casefold=True)


def _admin_console_help_response(reason):
    """HTML body for /console/... when misconfigured or wrong secret (avoids blank 'Not Found')."""
    if reason == "no_env":
        body = (
            "<p><strong>Private console URLs are off.</strong> <code>ADMIN_ACCESS_SECRET</code> is not set on "
            "this server, so <code>/console/…</code> will not work.</p>"
            "<p>To create an admin account without a private path, open "
            '<a href="/admin-setup.html"><code>/admin-setup.html</code></a> '
            "(requires <code>ADMIN_BOOTSTRAP_KEY</code> on the server).</p>"
            "<p>To use private URLs, set <code>ADMIN_ACCESS_SECRET</code> on the host to your chosen token, "
            "redeploy, then open <code>/console/&lt;that-token&gt;/create</code> .</p>"
        )
    else:
        body = (
            "<p><strong>This link does not match the server.</strong> The segment after <code>/console/</code> "
            "must exactly match <code>ADMIN_ACCESS_SECRET</code> (letters and digits are compared "
            "<strong>case-insensitively</strong>; check for typos or extra spaces in the Render env value).</p>"
        )
    html = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Admin console</title></head><body style=\"font-family:system-ui,sans-serif;max-width:40em;"
        "margin:2rem auto;padding:0 1.2rem;line-height:1.5;\">"
        "<h1 style=\"font-size:1.25rem;\">Admin console</h1>"
        f"{body}"
        "<p><a href=\"/\">Main app</a></p></body></html>"
    )
    return html, 404, {"Content-Type": "text/html; charset=utf-8"}


def _normalize_pmid(raw):
    s = re.sub(r"\D", "", str(raw or ""))
    if not s or len(s) > 12:
        return None
    return s


def literature_ordered_pmids(patient_login_username: str, limit: int = 25):
    """PubMed IDs from repository: global first, then patient-specific (deduped)."""
    uname = _norm(patient_login_username).lower()
    conn = get_conn()
    cursor = conn.cursor()
    out = []
    seen = set()
    run_execute(
        cursor,
        "SELECT pmid FROM literature_repository WHERE scope='global' ORDER BY created_at ASC",
    )
    for row in cursor.fetchall():
        p = _normalize_pmid(row[0])
        if p and p not in seen:
            seen.add(p)
            out.append(p)
        if len(out) >= limit:
            conn.close()
            return out
    if uname:
        run_execute(
            cursor,
            "SELECT pmid FROM literature_repository WHERE scope='patient' AND LOWER(patient_username)=? ORDER BY created_at ASC",
            (uname,),
        )
        for row in cursor.fetchall():
            p = _normalize_pmid(row[0])
            if p and p not in seen:
                seen.add(p)
                out.append(p)
            if len(out) >= limit:
                break
    conn.close()
    return out


@app.route("/api/literature", methods=["GET"])
def literature_list():
    """Curated PubMed links: all global rows, plus patient-specific when ?patient_username=."""
    patient_username = _norm(request.args.get("patient_username") or "").lower()
    conn = get_conn()
    cursor = conn.cursor()
    items = []
    run_execute(
        cursor,
        """SELECT id, scope, patient_username, pmid, curator_note, added_by, created_at
           FROM literature_repository WHERE scope='global' ORDER BY created_at ASC""",
    )
    for row in cursor.fetchall():
        items.append(
            {
                "id": row[0],
                "scope": row[1],
                "patient_username": row[2],
                "pmid": row[3],
                "curator_note": row[4],
                "added_by": row[5],
                "created_at": row[6],
            }
        )
    if patient_username:
        run_execute(
            cursor,
            """SELECT id, scope, patient_username, pmid, curator_note, added_by, created_at
               FROM literature_repository WHERE scope='patient' AND LOWER(patient_username)=?
               ORDER BY created_at ASC""",
            (patient_username,),
        )
        for row in cursor.fetchall():
            items.append(
                {
                    "id": row[0],
                    "scope": row[1],
                    "patient_username": row[2],
                    "pmid": row[3],
                    "curator_note": row[4],
                    "added_by": row[5],
                    "created_at": row[6],
                }
            )
    conn.close()
    return jsonify(items)


@app.route("/api/literature", methods=["POST"])
def literature_add():
    data = request.get_json() or {}
    scope = (data.get("scope") or "").strip().lower()
    pmid = _normalize_pmid(data.get("pmid"))
    if not pmid:
        return jsonify({"error": "Valid PubMed ID (PMID) required"}), 400
    if scope not in ("global", "patient"):
        return jsonify({"error": "scope must be global or patient"}), 400
    patient_username = None
    if scope == "patient":
        patient_username = _norm(data.get("patient_username") or "").lower()
        if not patient_username:
            return jsonify({"error": "patient_username required when scope is patient"}), 400
        conn = get_conn()
        cursor = conn.cursor()
        run_execute(
            cursor,
            "SELECT username, role FROM users WHERE LOWER(username)=?",
            (patient_username,),
        )
        prow = cursor.fetchone()
        conn.close()
        if not prow or str(prow[1] or "").lower() != "patient":
            return jsonify({"error": "patient_username must be a registered patient account"}), 400
    note = (data.get("curator_note") or "")[:2000]
    added_by = _norm(data.get("added_by") or "")[:120]
    ts = int(datetime.now().timestamp() * 1000)
    conn = get_conn()
    cursor = conn.cursor()
    try:
        if USE_PG:
            cursor.execute(
                """INSERT INTO literature_repository (scope, patient_username, pmid, curator_note, added_by, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                (
                    scope,
                    patient_username if scope == "patient" else None,
                    pmid,
                    note or None,
                    added_by or None,
                    ts,
                ),
            )
            new_id = cursor.fetchone()[0]
        else:
            run_execute(
                cursor,
                """INSERT INTO literature_repository (scope, patient_username, pmid, curator_note, added_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    scope,
                    patient_username if scope == "patient" else None,
                    pmid,
                    note or None,
                    added_by or None,
                    ts,
                ),
            )
            new_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        conn.rollback()
        err = str(e).lower()
        if "unique" in err or "integrity" in err:
            return jsonify({"error": "This PMID is already in the repository for that scope"}), 409
        raise
    finally:
        conn.close()
    _notify_literature_webhook(scope, pmid, added_by, note, patient_username)
    return jsonify(
        {
            "id": new_id,
            "scope": scope,
            "patient_username": patient_username,
            "pmid": pmid,
            "curator_note": note,
            "added_by": added_by,
            "created_at": ts,
        }
    )


@app.route("/api/literature/<int:item_id>", methods=["DELETE"])
def literature_delete(item_id):
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor, "DELETE FROM literature_repository WHERE id=?", (item_id,))
    deleted = cursor.rowcount if hasattr(cursor, "rowcount") else 0
    conn.commit()
    conn.close()
    if not deleted:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"message": "Removed"})


@app.route("/api/feedback/config", methods=["GET"])
def feedback_public_config():
    """Non-secret hints for organizers (Render env checklist). No authentication."""
    return jsonify(
        {
            "uses_private_console": bool(_admin_access_secret()),
            "bootstrap_key_configured": bool(_admin_bootstrap_key()),
            "notification_webhook_configured": bool(
                (os.environ.get("FEEDBACK_NOTIFY_WEBHOOK") or "").strip()
            ),
            "feedback_admin_usernames_configured": bool(_parse_feedback_admin_usernames()),
            "feedback_auth_secret_configured": bool((os.environ.get("FEEDBACK_AUTH_SECRET") or "").strip()),
            "feedback_email_smtp_configured": bool(_feedback_smtp_configured()),
            "literature_notify_webhook_configured": bool(
                (os.environ.get("LITERATURE_NOTIFY_WEBHOOK") or "").strip()
            ),
        }
    )


@app.route("/api/feedback", methods=["POST"])
def feedback_submit():
    """Submit feedback only after a real login: signed feedback_token from /api/users/login, or password in body."""
    data = request.get_json() or {}
    uname = _norm(data.get("username") or "").lower()
    pwd = _norm(data.get("password") or "")
    token = (data.get("feedback_token") or data.get("feedbackToken") or "").strip()
    user = None
    if pwd:
        user = _verify_user_credentials(uname, pwd)
        if not user:
            return jsonify({"error": "Invalid username or password"}), 401
    elif token:
        if not uname:
            return jsonify({"error": "Username is required with your feedback session."}), 400
        if _verify_feedback_token(uname, token):
            user = _lookup_feedback_submitter(uname)
            if not user:
                return jsonify({"error": "Unknown username."}), 400
        else:
            return jsonify(
                {
                    "error": "Please log out, log in again, then try sending feedback.",
                    "code": "feedback_token_invalid",
                }
            ), 401
    else:
        return jsonify(
            {
                "error": "Log in again to send feedback (session not loaded).",
                "code": "feedback_token_missing",
            }
        ), 401
    role_l = _norm(user.get("role") or "").lower()
    if role_l not in ("patient", "doctor", "admin"):
        return jsonify({"error": "This account cannot submit feedback through this form."}), 403
    msg = (data.get("message") or "").strip()
    if len(msg) < 4:
        return jsonify({"error": "Please enter a slightly longer message (at least 4 characters)."}), 400
    if len(msg) > 8000:
        msg = msg[:8000]
    if role_l == "admin":
        source = "admin"
    elif role_l == "patient":
        source = "patient"
    else:
        source = "doctor"
    ts = int(datetime.now().timestamp() * 1000)
    conn = get_conn()
    cursor = conn.cursor()
    try:
        if USE_PG:
            cursor.execute(
                """INSERT INTO user_feedback (username, role, message, source, created_at)
                   VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (user["username"], user["role"], msg, source, ts),
            )
            new_id = cursor.fetchone()[0]
        else:
            run_execute(
                cursor,
                """INSERT INTO user_feedback (username, role, message, source, created_at)
                   VALUES (?,?,?,?,?)""",
                (user["username"], user["role"], msg, source, ts),
            )
            new_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    _notify_feedback_webhook(user["username"], user["role"], msg, source, ts)
    _notify_feedback_email(user["username"], user["role"], msg, source, ts, new_id)
    return jsonify({"id": new_id, "message": "Thank you — your feedback was received."})


@app.route("/api/feedback/admin/list", methods=["POST"])
def feedback_admin_list():
    """List feedback for admins (FEEDBACK_ADMIN_USERNAMES env and/or role Admin)."""
    data = request.get_json() or {}
    user = _verify_user_credentials(data.get("username"), data.get("password"))
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401
    if not _can_view_feedback_admin(user):
        return jsonify(
            {
                "error": "Not authorized. Set FEEDBACK_ADMIN_USERNAMES on the server (comma-separated "
                "usernames) or use an account with role Admin."
            }
        ), 403
    filt_src = _norm(data.get("filter_source") or "").lower()
    filt_role = _norm(data.get("filter_role") or "").lower()
    search = _norm(data.get("search") or "").lower()

    clauses = []
    params = []
    if filt_src in ("patient", "doctor", "admin"):
        clauses.append("LOWER(TRIM(COALESCE(source,'')))=?")
        params.append(filt_src)
    if filt_role in ("patient", "doctor", "admin"):
        clauses.append("LOWER(TRIM(COALESCE(role,'')))=?")
        params.append(filt_role)
    if search:
        like = "%" + search.replace("%", "").replace("_", "") + "%"
        clauses.append(
            "(LOWER(COALESCE(message,'')) LIKE ? OR LOWER(COALESCE(username,'')) LIKE ?)"
        )
        params.extend([like, like])

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT id, username, role, message, source, created_at FROM user_feedback"
        + where_sql
        + " ORDER BY created_at DESC LIMIT 500"
    )
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor, sql, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    items = [
        {
            "id": r[0],
            "username": r[1],
            "role": r[2],
            "message": r[3],
            "source": r[4] or "",
            "created_at": r[5],
        }
        for r in rows
    ]
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/ai/admin/list", methods=["POST"])
def ai_chat_admin_list():
    """List saved AI Q&A for admins (same auth as feedback admin)."""
    data = request.get_json() or {}
    user = _verify_user_credentials(data.get("username"), data.get("password"))
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401
    if not _can_view_feedback_admin(user):
        return jsonify(
            {
                "error": "Not authorized. Set FEEDBACK_ADMIN_USERNAMES on the server (comma-separated "
                "usernames) or use an account with role Admin."
            }
        ), 403

    filt_src = _norm(data.get("filter_source") or "").lower()
    errors_only = bool(data.get("errors_only"))
    search = _norm(data.get("search") or "").lower()

    clauses = []
    params = []
    if filt_src in ("patient", "doctor"):
        clauses.append("LOWER(TRIM(COALESCE(source,'')))=?")
        params.append(filt_src)
    if errors_only:
        clauses.append("(success=0 OR TRIM(COALESCE(error_message,''))<>'')")
    if search:
        like = "%" + search.replace("%", "").replace("_", "") + "%"
        clauses.append(
            "(LOWER(COALESCE(question,'')) LIKE ? OR LOWER(COALESCE(response,'')) LIKE ? "
            "OR LOWER(COALESCE(error_message,'')) LIKE ? OR LOWER(COALESCE(username,'')) LIKE ?)"
        )
        params.extend([like, like, like, like])

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT id, created_at, username, display_name, role, context_username, source, "
        "question, response, references_json, model, success, error_message, had_image, "
        "rating, rated_at "
        "FROM ai_chat_log"
        + where_sql
        + " ORDER BY created_at DESC LIMIT 500"
    )
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor, sql, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        refs = []
        if r[9]:
            try:
                refs = json.loads(r[9])
            except (TypeError, ValueError):
                refs = []
        items.append(
            {
                "id": r[0],
                "created_at": r[1],
                "username": r[2],
                "display_name": r[3] or "",
                "role": r[4] or "",
                "context_username": r[5] or "",
                "source": r[6] or "",
                "question": r[7] or "",
                "response": r[8] or "",
                "references": refs,
                "references_count": len(refs) if isinstance(refs, list) else 0,
                "model": r[10] or "",
                "success": bool(r[11]),
                "error_message": r[12] or "",
                "had_image": bool(r[13]),
                "rating": r[14] if len(r) > 14 else None,
                "rated_at": r[15] if len(r) > 15 else None,
            }
        )
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/ai/rate", methods=["POST"])
def rate_ai_response():
    """Thumbs up (1) or down (-1) on a logged AI reply; 0 clears the rating."""
    data = request.get_json() or {}
    log_id = data.get("log_id")
    username = _norm(data.get("username") or "").lower()
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return jsonify({"error": "rating must be 1, -1, or 0"}), 400
    if rating not in (1, -1, 0):
        return jsonify({"error": "rating must be 1, -1, or 0"}), 400
    if not log_id or not username:
        return jsonify({"error": "log_id and username are required"}), 400
    try:
        log_id = int(log_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid log_id"}), 400

    conn = get_conn()
    cursor = conn.cursor()
    run_execute(
        cursor,
        "SELECT username FROM ai_chat_log WHERE id=?",
        (log_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "AI response not found"}), 404
    owner = _norm(row[0] or "").lower()
    if owner != username:
        conn.close()
        return jsonify({"error": "Not allowed to rate this response"}), 403

    rated_at = int(datetime.now().timestamp() * 1000) if rating != 0 else None
    db_rating = rating if rating != 0 else None
    run_execute(
        cursor,
        "UPDATE ai_chat_log SET rating=?, rated_at=? WHERE id=?",
        (db_rating, rated_at, log_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "log_id": log_id, "rating": db_rating})


@app.route("/api/admin/bootstrap", methods=["POST"])
def admin_bootstrap_create():
    """Create an Admin user when ADMIN_BOOTSTRAP_KEY matches (not available via public registration)."""
    expected = _admin_bootstrap_key()
    if not expected:
        return jsonify(
            {"error": "Admin bootstrap is not enabled. Set ADMIN_BOOTSTRAP_KEY on the server."}
        ), 503
    data = request.get_json() or {}
    submitted = _strip_wrapping_quotes_value(data.get("bootstrap_key") or "")
    if not _const_time_str_equal(expected, submitted):
        return jsonify({"error": "Invalid bootstrap key."}), 403
    username = _norm(data.get("username") or "").lower()
    password = _norm(data.get("password") or "")
    name = _norm(data.get("name") or "")
    if not all([username, password, name]):
        return jsonify({"error": "Username, password, and name are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    role = "Admin"
    conn = get_conn()
    cursor = conn.cursor()
    try:
        if USE_PG:
            cursor.execute(
                "INSERT INTO users (username, password, name, role, patient_id) VALUES (%s,%s,%s,%s,%s)",
                (username, password, name, role, None),
            )
        else:
            run_execute(
                cursor,
                "INSERT INTO users (username, password, name, role, patient_id) VALUES (?, ?, ?, ?, ?)",
                (username, password, name, role, None),
            )
        conn.commit()
        conn.close()
        return jsonify(
            {"message": "Admin account created. Sign in using your admin console URL to view feedback."}
        ), 201
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        err = str(e).lower()
        if "unique" in err or "integrity" in err or isinstance(e, sqlite3.IntegrityError):
            return jsonify({"error": "Username already taken."}), 409
        raise


@app.route('/api/users/login', methods=['POST'])
def login():
    """User login. Normalizes username/password (strip + NFKC) so different devices match."""
    data = request.get_json() or {}
    username = _norm(data.get('username') or '').lower()
    password = _norm(data.get('password') or '')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor,
        "SELECT username, password, name, role, patient_id, age, sex FROM users WHERE username=?",
        (username,)
    )
    row = cursor.fetchone()
    # Compare normalized passwords so stored (legacy) and input match across devices
    stored_pass = (row[1] or '') if row and len(row) > 1 else ''
    user = row if row and _norm(stored_pass) == password else None
    
    if user:
        # If patient doesn't have an ID, generate one
        patient_id = user[4] or ""
        if user[3].lower() == 'patient' and not patient_id:
            patient_id = generate_patient_id()
            run_execute(cursor,"UPDATE users SET patient_id=? WHERE username=?", (patient_id, user[0]))
            conn.commit()
            print(f"Generated Patient ID {patient_id} for {user[0]}")
        
        conn.close()
        fb_tok = _make_feedback_token(user[0])
        onboarding_completed = _user_onboarding_completed(user[0])
        return jsonify(
            {
                "username": user[0],
                "name": user[2],
                "role": user[3],
                "patient_id": patient_id,
                "age": user[5] if user[5] else None,
                "sex": user[6] if len(user) > 6 and user[6] else "",
                "feedback_token": fb_tok,
                "onboarding_completed": onboarding_completed,
            }
        )
    else:
        # Log for debugging cross-device login: does this username exist?
        user_exists = row is not None
        print(f"Login failed: username={username!r}, user_exists={user_exists} (check Render logs if cross-device)")
        conn.close()
        return jsonify({"error": "Invalid username or password"}), 401

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user. Normalizes username/password (strip + NFKC) for cross-device login."""
    data = request.get_json() or {}
    username = _norm(data.get('username') or '').lower()
    password = _norm(data.get('password') or '')
    name = _norm(data.get('name') or '')
    role = _norm(data.get('role') or 'Patient')
    
    if not all([username, password, name]):
        return jsonify({"error": "Username, password, and name are required"}), 400

    if role.lower() == "admin":
        return jsonify(
            {
                "error": "Admin accounts cannot be created from the public sign-up form. "
                "Use the private admin setup URL and server bootstrap key from your operator."
            }
        ), 403
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Generate patient_id for all users (patients and doctors can have one, but it's mainly for patients)
    patient_id = None
    if role.lower() == 'patient':
        # Keep generating until we get a unique one
        while True:
            new_id = generate_patient_id()
            run_execute(cursor,"SELECT username FROM users WHERE patient_id=?", (new_id,))
            if not cursor.fetchone():
                patient_id = new_id
                break
    
    try:
        onboarding_done = 0 if role.lower() == 'patient' else 1
        run_execute(cursor,
            "INSERT INTO users (username, password, name, role, patient_id, onboarding_completed) VALUES (?, ?, ?, ?, ?, ?)",
            (username, password, name, role, patient_id, onboarding_done)
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
        conn = get_conn()
        cursor = conn.cursor()
        
        print(f"Querying user: {username.lower()}")
        run_execute(cursor,
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
            run_execute(cursor,"UPDATE users SET patient_id=? WHERE username=?", (patient_id, user[0]))
            conn.commit()
            user = (user[0], user[1], user[2], patient_id, user[4], user[5], user[6], user[7], user[8], user[9], user[10])
            print(f"Generated Patient ID {patient_id} for {user[0]}")
        
        # Get medical info if user exists
        medical_info = None
        try:
            print("Loading medical info...")
            try:
                run_execute(cursor,
                    """SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications,
                       height, weight, sex, height_feet, height_inches, waist_cm, hip_cm, body_fat_pct, lean_mass_kg,
                       weight_units, height_units, diabetes_type, chronic_conditions, weekly_food_budget, activity_level
                       FROM patient_medical_info WHERE username=?""",
                    (username.lower(),)
                )
            except sqlite3.OperationalError:
                run_execute(cursor,
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
            "medical_info": medical_info,
            "onboarding_completed": _user_onboarding_completed(user[0]),
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
    conn = get_conn()
    cursor = conn.cursor()
    try:
        run_execute(cursor,
            "SELECT username, name, patient_id FROM users WHERE role='Patient' ORDER BY LOWER(name), username"
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        run_execute(cursor,
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
    conn = get_conn()
    cursor = conn.cursor()
    try:
        run_execute(cursor,
            "SELECT username, name, role, patient_id, age, sex, date_of_birth, middle_initial, last_name, biological_sex, gender_identity FROM users WHERE role='Patient'"
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        run_execute(cursor,"SELECT username, name, role, patient_id, age, sex FROM users WHERE role='Patient'")
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
        conn = get_conn()
        cursor = conn.cursor()
        try:
            run_execute(cursor,
                "SELECT username, name, role, patient_id, age, sex, date_of_birth, middle_initial, last_name, biological_sex, gender_identity FROM users WHERE patient_id=?",
                (patient_id,)
            )
        except sqlite3.OperationalError:
            run_execute(cursor,"SELECT username, name, role, patient_id, age, sex FROM users WHERE patient_id=?", (patient_id,))
        user = cursor.fetchone()
        if user:
            user = list(user) + [None] * (11 - len(user))
            user = tuple(user[:11])
        
        medical_info = None
        if user:
            try:
                run_execute(cursor,
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
    conn = get_conn()
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
        run_execute(cursor,f"UPDATE users SET {', '.join(updates)} WHERE username=?", values)
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
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor,
        "SELECT likes, dislikes, religion, culture FROM preferences WHERE username=?",
        (username.lower(),)
    )
    prefs = cursor.fetchone()
    conn.close()
    
    if prefs:
        return jsonify({
            "likes": prefs[0] or "",
            "dislikes": prefs[1] or "",
            "religion": (prefs[2] or "") if len(prefs) > 2 else "",
            "culture": (prefs[3] or "") if len(prefs) > 3 else "",
        })
    else:
        return jsonify({"likes": "", "dislikes": "", "religion": "", "culture": ""})


@app.route('/api/users/by-patient-id/<patient_id>/preferences', methods=['GET'])
def get_preferences_by_patient_id(patient_id):
    """Get preferences by patient_id (tries resolved username, then username=patient_id)."""
    pid = str(patient_id).strip()
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor,"SELECT username FROM users WHERE patient_id=?", (pid,))
    row = cursor.fetchone()
    username = row[0] if row else None
    out = {"likes": "", "dislikes": "", "religion": "", "culture": ""}
    for uname in ([username] if username else []) + ([pid] if pid else []):
        if not uname:
            continue
        run_execute(cursor,"SELECT likes, dislikes, religion, culture FROM preferences WHERE username=?", (uname.lower(),))
        prefs = cursor.fetchone()
        if not prefs:
            run_execute(cursor,"SELECT likes, dislikes, religion, culture FROM preferences WHERE username=?", (uname,))
            prefs = cursor.fetchone()
        if prefs and (prefs[0] or prefs[1] or (len(prefs) > 2 and prefs[2]) or (len(prefs) > 3 and prefs[3])):
            out = {
                "likes": prefs[0] or "",
                "dislikes": prefs[1] or "",
                "religion": (prefs[2] or "") if len(prefs) > 2 else "",
                "culture": (prefs[3] or "") if len(prefs) > 3 else "",
            }
            break
    conn.close()
    return jsonify(out)

@app.route('/api/users/<username>/preferences', methods=['POST'])
def update_preferences(username):
    """Update user preferences"""
    data = request.get_json() or {}
    likes = data.get('likes', '')
    dislikes = data.get('dislikes', '')
    religion = (data.get('religion') or '')[:1000]
    culture = (data.get('culture') or '')[:1000]
    
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor,
        """INSERT INTO preferences (username, likes, dislikes, religion, culture) 
           VALUES (?, ?, ?, ?, ?) 
           ON CONFLICT(username) DO UPDATE SET
             likes=excluded.likes, dislikes=excluded.dislikes,
             religion=excluded.religion, culture=excluded.culture""",
        (username.lower(), likes, dislikes, religion, culture)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Preferences updated successfully"})

@app.route('/api/users/<username>/notes', methods=['GET'])
def get_notes(username):
    """Get doctor notes for a user (case-insensitive username match)."""
    conn = get_conn()
    cursor = conn.cursor()
    uname_lower = username.lower() if username else ""
    run_execute(cursor,
        "SELECT note, created_at FROM notes WHERE LOWER(username)=? ORDER BY created_at DESC",
        (uname_lower,)
    )
    notes = cursor.fetchall()
    run_execute(cursor,"SELECT username FROM notes")
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
    conn = get_conn()
    cursor = conn.cursor()
    pid = str(patient_id).strip()
    run_execute(cursor,"SELECT username FROM users WHERE patient_id=?", (pid,))
    row = cursor.fetchone()
    username = row[0] if row else None
    uname_lower = (username or "").lower()
    run_execute(cursor,
        "SELECT note, created_at FROM notes WHERE LOWER(username)=? ORDER BY created_at DESC",
        (uname_lower,)
    )
    notes = cursor.fetchall()
    # If no notes under username, also check under patient_id (doctor may have stored notes that way)
    if len(notes) == 0 and pid:
        run_execute(cursor,
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
    run_execute(cursor,
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
    conn = get_conn()
    cursor = conn.cursor()
    result = _notes_summary_for_username(cursor, username)
    conn.close()
    print(f"[notes/summary] username={username!r} -> {result['total_notes']} notes")
    return jsonify(result)


@app.route('/api/users/by-patient-id/<patient_id>/notes/summary', methods=['GET'])
def get_notes_summary_by_patient_id(patient_id):
    """Get notes summary by patient ID (so patient always gets their notes)."""
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor,"SELECT username FROM users WHERE patient_id=?", (str(patient_id).strip(),))
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
    
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor,
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
    conn = get_conn()
    cursor = conn.cursor()
    try:
        run_execute(cursor,
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
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor,"SELECT username FROM users WHERE patient_id=?", (pid,))
    row = cursor.fetchone()
    username = row[0] if row else None
    for uname in ([username] if username else []) + ([pid] if pid else []):
        if not uname:
            continue
        try:
            run_execute(cursor,
                """SELECT past_medical_history, patient_goals, food_allergies, physical_activity, current_medications,
                   height, weight, sex, height_feet, height_inches, waist_cm, hip_cm, body_fat_pct, lean_mass_kg,
                   weight_units, height_units, diabetes_type, chronic_conditions, weekly_food_budget, activity_level
                   FROM patient_medical_info WHERE username=?""",
                (uname.lower(),)
            )
            med = cursor.fetchone()
            if not med:
                run_execute(cursor,
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
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor,
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

# Every AI reply must include citations (prepended as first system message on every request)
AI_CITATION_RULE_DOCTOR = """Citation rule (applies to EVERY reply, no exceptions—including brief answers, follow-ups, and clarifications):
After your main answer, add a section with this exact heading on its own line:
**Supporting references**
Then 1–3 bullet points ONLY—each must directly support a specific claim in your answer above.

Relevance gate (critical):
- Read each provided source block (web search, PubMed, openFDA, literature repository) before citing. Use a source ONLY if its title/excerpt clearly relates to the user's question.
- If a provided source is off-topic, skip it entirely. Never cite random or tangential articles to fill space.
- If no provided source fits, do not cite them. Instead give 1 bullet naming a trusted guideline body (e.g. ADA, WHO, NHS) relevant to the topic—no invented URLs.

Linking:
- Web search: markdown [title](url) using ONLY "URL:" lines from the web search block for facts you used.
- PubMed/repository: markdown [short title](https://pubmed.ncbi.nlm.nih.gov/PMID/) for articles you actually relied on.
- Never invent PMIDs, DOIs, or URLs.

Evidence discipline: PubMed/openFDA/web/repository excerpts are optional background—not a checklist. Ignore unrelated snippets. For calories/BMR/TDEE, derive from explicit patient metrics or label as general educational estimates."""

ONBOARDING_START_TOKEN = "__ONBOARDING_START__"

AI_PATIENT_ONBOARDING_PROMPT = """You are conducting a warm welcome interview for {user_name}, a new patient using Wellbeing Companion.
Your job is to get to know them through a short, friendly conversation—not a medical exam.

Interview rules:
- Ask ONE question at a time. Keep each reply to 2–4 short sentences.
- Briefly acknowledge their last answer before asking the next question.
- Over the conversation, learn about: their main wellbeing or nutrition goals; foods they enjoy; foods they avoid or dislike; food allergies; religious or cultural food practices that matter to them (e.g. halal, kosher, fasting, vegetarian traditions, cultural cuisines); their cultural background if they want to share; how active they are; anything important for their doctor or care team to know; age and sex if they are comfortable sharing.
- Do not lecture, diagnose, or give long advice yet—focus on listening and asking.
- When you have covered goals, likes/dislikes, religion/culture (if they wish to share), activity, and allergies (or they say they have none), give a short friendly summary of what you learned and tell them they can tap **Save intro to my profile** when ready, or keep chatting if they want to add more.
- Never invent facts they did not share.

Citation rule during this interview only: after your reply, add **Supporting references** with exactly ONE brief bullet (e.g. general NHS or WHO wellbeing guidance)—no URLs required."""

AI_CITATION_RULE_PATIENT = """Citation rule (applies to EVERY reply, no exceptions—including short answers and follow-ups):
After your main answer, add a section with this exact heading on its own line:
**Supporting references**
Then 1–3 bullet points ONLY—each must directly support something you said in your answer.

Relevance gate (critical):
- Before citing any provided source (web search, PubMed, openFDA, literature repository), check that its title/excerpt clearly matches the user's question.
- Skip off-topic sources completely. Never list random studies or links just to have references.
- If nothing provided fits, use 1 bullet citing a well-known organization relevant to the topic (e.g. NHS, WHO, ADA)—by name only, no invented URLs.
- If you relied mainly on this app's profile/notes, say so in one bullet.

Linking:
- Web: [title](url) with URLs copied exactly from the web search block.
- PubMed: [short title](https://pubmed.ncbi.nlm.nih.gov/PMID/) only for articles you used.
- Never fabricate links or PMIDs.

Evidence discipline: Ignore unrelated PubMed/web/repository snippets. For calorie or body-composition numbers, say they are estimates unless calculated from saved profile data; encourage checking with the care team when unsure."""


def _tavily_health_domains():
    raw = os.environ.get('AI_WEB_SEARCH_DOMAINS', '').strip()
    if raw:
        return [d.strip() for d in raw.split(',') if d.strip()]
    return [
        'nih.gov', 'nhs.uk', 'who.int', 'cdc.gov', 'pubmed.ncbi.nlm.nih.gov',
        'diabetes.org', 'heart.org', 'cancer.gov', 'medlineplus.gov', 'fda.gov',
    ]


def tavily_web_search(query: str, max_results: int = 4):
    """
    Search the web via Tavily (https://tavily.com). Set TAVILY_API_KEY in the environment.
    Returns a plain-text block for the model, or None if disabled / error.
    """
    api_key = os.environ.get('TAVILY_API_KEY')
    if not api_key or not query or len(query.strip()) < 4:
        return None
    if os.environ.get('AI_WEB_SEARCH', '1').strip().lower() in ('0', 'false', 'no', 'off'):
        return None
    try:
        import httpx
        q = query.strip()[:500]
        base_payload = {
            'api_key': api_key,
            'query': q,
            'search_depth': 'advanced',
            'max_results': max_results,
            'include_answer': False,
        }
        results = []
        for payload in (
            {**base_payload, 'include_domains': _tavily_health_domains()},
            base_payload,
        ):
            resp = httpx.post('https://api.tavily.com/search', json=payload, timeout=22.0)
            resp.raise_for_status()
            data = resp.json()
            results = data.get('results') or []
            if results:
                break
        if not results:
            return None
        lines = [
            '--- Web search results (cite ONLY if excerpt is relevant to the user question) ---',
            'Ignore any result whose snippet does not match the question. Use markdown links only for results you actually used.',
        ]
        for i, r in enumerate(results, 1):
            title = (r.get('title') or 'Source')[:220]
            url = (r.get('url') or '').strip()
            content = (r.get('content') or '')[:700]
            if not url:
                continue
            lines.append(f'[{i}] {title}\nURL: {url}\n{content}\n')
        return '\n'.join(lines) if len(lines) > 2 else None
    except Exception as e:
        print(f'Tavily web search error: {e}')
        return None


def _openai_advice_model_id(has_image: bool) -> str:
    """Chat model for /api/ai/advice. Override with fine-tuned IDs, e.g. ft:gpt-4o-mini:acme:custom:7q8m."""
    if has_image:
        custom = (os.environ.get("OPENAI_ADVICE_MODEL_VISION") or "").strip()
        return custom if custom else "gpt-4o-mini"
    custom = (os.environ.get("OPENAI_ADVICE_MODEL") or "").strip()
    return custom if custom else "gpt-3.5-turbo"


def _openai_nutrition_model_id() -> str:
    """Chat model for /api/ai/nutrition-plan."""
    custom = (os.environ.get("OPENAI_NUTRITION_MODEL") or "").strip()
    return custom if custom else "gpt-3.5-turbo"


def _notify_literature_webhook(scope, pmid, added_by, note, patient_username):
    """Optional Discord/Slack/Zapier: JSON POST when a PMID is added to the repository."""
    url = (os.environ.get("LITERATURE_NOTIFY_WEBHOOK") or "").strip()
    if not url:
        return
    snippet = (note or "").replace("\r", " ").strip()
    if len(snippet) > 800:
        snippet = snippet[:797] + "..."
    summary = (
        f"[Wellbeing Companion] Literature repository\n"
        f"Scope: {scope}\nPMID: {pmid}\n"
        f"Patient: {patient_username or '—'}\nAdded by: {added_by or '—'}\n"
        f"Note: {snippet or '—'}"
    )
    payload = {
        "text": summary,
        "scope": scope,
        "pmid": pmid,
        "patient_username": patient_username,
        "added_by": added_by,
        "curator_note": note,
    }
    if "discord.com/api/webhooks" in url.lower() or "discordapp.com/api/webhooks" in url.lower():
        payload["content"] = summary[:1990]
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        timeout = float((os.environ.get("FEEDBACK_NOTIFY_WEBHOOK_TIMEOUT_SEC") or "25").strip())
        if timeout < 5 or timeout > 120:
            timeout = 25.0
    except ValueError:
        timeout = 25.0
    try:
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "WellbeingCompanion/1.0 (+literature-webhook)",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1024)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read()[:800].decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        print(
            f"LITERATURE_NOTIFY_WEBHOOK HTTP {e.code} for {url[:80]}...: {detail or e.reason}"
        )
    except Exception as ex:
        print(f"LITERATURE_NOTIFY_WEBHOOK request failed: {ex}")


def _nutrition_sex_low(sex_raw):
    s = _norm(sex_raw or "").lower()
    if s.startswith("m"):
        return "m"
    return "f"


def _nutrition_weight_kg(weight_str):
    if weight_str is None or str(weight_str).strip() == "":
        return None
    s = str(weight_str).lower().replace(",", "")
    m = re.search(r"([\d.]+)\s*(kg|kilos?)\b", s)
    if m:
        return float(m.group(1))
    m = re.search(r"([\d.]+)\s*(lb|lbs|pounds?)\b", s)
    if m:
        return float(m.group(1)) * 0.45359237
    m = re.search(r"([\d.]+)", s)
    if m:
        return float(m.group(1)) * 0.45359237
    return None


def _nutrition_height_cm(height_text, feet, inches):
    if feet not in (None, "") or inches not in (None, ""):
        try:
            ft = float(feet or 0)
            inc = float(inches or 0)
            total_in = ft * 12 + inc
            if total_in > 0:
                return round(total_in * 2.54, 1)
        except (TypeError, ValueError):
            pass
    t = _norm(height_text or "")
    m = re.search(r"(\d+\.?\d*)\s*cm", t, re.I)
    if m:
        return round(float(m.group(1)), 1)
    m = re.search(r"(\d+)\s*['′]\s*(\d+(?:\.\d+)?)\s*[\"″]?", t)
    if m:
        total_in = int(m.group(1)) * 12 + float(m.group(2))
        return round(total_in * 2.54, 1)
    return None


def _nutrition_activity_multiplier(activity_level, physical_activity):
    t = f"{activity_level or ''} {physical_activity or ''}".lower()
    if any(x in t for x in ("sedentary", "desk", "little exercise", "none")):
        return 1.2
    if any(x in t for x in ("very active", "extremely", "athlete", "heavy exercise")):
        return 1.725
    if any(x in t for x in ("moderate", "medium", "regular")):
        return 1.55
    if any(x in t for x in ("light", "lightly", "walking")):
        return 1.375
    return 1.375


def _nutrition_bmr_mifflin(weight_kg, height_cm, age, sex_low):
    if weight_kg is None or height_cm is None or age is None:
        return None
    try:
        a = int(age)
        w = float(weight_kg)
        h = float(height_cm)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0 or a < 14 or a > 120:
        return None
    base = 10 * w + 6.25 * h - 5 * a
    return base + 5 if str(sex_low or "f").startswith("m") else base - 161


def _nutrition_maintenance_estimate(weight_kg, height_cm, age, sex_raw, activity_level, physical_activity):
    """Rough TDEE (kcal/day) when biometrics exist; otherwise None."""
    sex_l = _nutrition_sex_low(sex_raw)
    bmr = _nutrition_bmr_mifflin(weight_kg, height_cm, age, sex_l)
    if bmr is None:
        return None, []
    af = _nutrition_activity_multiplier(activity_level, physical_activity)
    td = round(bmr * af)
    notes = [f"Estimated maintenance ~{td} kcal/day (Mifflin-St Jeor BMR × activity factor)."]
    return td, notes


def _nutrition_weight_loss_floor_kcal(age, sex_low):
    if age and age < 18:
        return 1400
    if str(sex_low or "f").startswith("m"):
        return 1500
    return 1200


def _plan_parse_int_calories(val):
    if val is None:
        return None
    m = re.search(r"-?\d+", str(val))
    if not m:
        return None
    return int(m.group(0))


def _plan_store_calories(plan, key, n):
    plan[key] = str(int(round(n)))


def _nutrition_clamp_plan(plan, maintenance_target, sex_raw, age):
    """Coerce AI calorie fields toward safe, internally consistent ranges."""
    notes = []
    if not isinstance(plan, dict):
        return plan, notes
    sex_l = _nutrition_sex_low(sex_raw)
    floor_loss = _nutrition_weight_loss_floor_kcal(age, sex_l)
    maint = _plan_parse_int_calories(plan.get("maintenance_calories"))
    loss = _plan_parse_int_calories(plan.get("weight_loss_calories"))
    if maint is None or loss is None:
        return plan, notes

    if maintenance_target and maintenance_target > 0:
        snap = int(round(maintenance_target))
        if snap > 0 and abs(maint - snap) / snap > 0.22:
            notes.append(
                f"Adjusted maintenance calories from {maint} toward ~{snap} kcal/day based on height/weight/age/activity."
            )
            maint = snap
        maint = max(900, min(maint, int(snap * 1.12) if snap else maint))
    else:
        maint = max(1000, maint)

    hi_loss = maint - 300
    if hi_loss <= floor_loss:
        notes.append(
            "Incomplete height/weight/age data: calorie targets kept conservative — verify with a clinician."
        )
        loss = max(floor_loss, min(loss, max(maint - 250, floor_loss)))
    else:
        if loss < floor_loss:
            notes.append(f"Raised weight-loss calories to safe minimum (~{floor_loss} kcal/day) for stated sex/age group.")
            loss = floor_loss
        if loss > hi_loss:
            notes.append(f"Capped weight-loss calories at {hi_loss} so intake stays ≥300 kcal below maintenance.")
            loss = hi_loss
        if loss >= maint:
            loss = max(floor_loss, maint - 500)
            notes.append("Adjusted weight-loss calories to sit below maintenance with a modest deficit.")

    _plan_store_calories(plan, "maintenance_calories", maint)
    _plan_store_calories(plan, "weight_loss_calories", loss)
    return plan, notes


def _format_onboarding_transcript(conversation_history):
    lines = []
    for msg in conversation_history or []:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content or content == ONBOARDING_START_TOKEN:
            continue
        if role == "user":
            lines.append(f"Patient: {content}")
        elif role == "assistant":
            lines.append(f"AI: {content}")
    return "\n".join(lines)


def _save_onboarding_profile(username, extracted):
    """Write extracted interview fields to preferences, medical_info, and users."""
    uname = _norm(username or "").lower()
    if not uname or not isinstance(extracted, dict):
        return
    likes = (extracted.get("likes") or "").strip()[:4000]
    dislikes = (extracted.get("dislikes") or "").strip()[:4000]
    religion = (extracted.get("religion") or "").strip()[:1000]
    culture = (extracted.get("culture") or "").strip()[:1000]
    conn = get_conn()
    cursor = conn.cursor()
    run_execute(
        cursor,
        """INSERT INTO preferences (username, likes, dislikes, religion, culture) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(username) DO UPDATE SET
             likes=excluded.likes, dislikes=excluded.dislikes,
             religion=excluded.religion, culture=excluded.culture""",
        (uname, likes, dislikes, religion, culture),
    )
    med_fields = {
        "patient_goals": (extracted.get("patient_goals") or "")[:4000],
        "food_allergies": (extracted.get("food_allergies") or "")[:2000],
        "physical_activity": (extracted.get("physical_activity") or "")[:2000],
        "activity_level": (extracted.get("activity_level") or "")[:200],
        "past_medical_history": (extracted.get("past_medical_history") or "")[:4000],
    }
    run_execute(
        cursor,
        """INSERT INTO patient_medical_info (username, patient_goals, food_allergies, physical_activity, activity_level, past_medical_history)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(username) DO UPDATE SET
             patient_goals=excluded.patient_goals,
             food_allergies=excluded.food_allergies,
             physical_activity=excluded.physical_activity,
             activity_level=excluded.activity_level,
             past_medical_history=excluded.past_medical_history""",
        (
            uname,
            med_fields["patient_goals"],
            med_fields["food_allergies"],
            med_fields["physical_activity"],
            med_fields["activity_level"],
            med_fields["past_medical_history"],
        ),
    )
    age_val = extracted.get("age")
    sex_val = (extracted.get("sex") or "").strip()[:64]
    try:
        age_int = int(age_val) if age_val is not None and str(age_val).strip() != "" else None
    except (TypeError, ValueError):
        age_int = None
    if age_int is not None or sex_val:
        if age_int is not None and sex_val:
            run_execute(cursor, "UPDATE users SET age=?, sex=? WHERE LOWER(username)=?", (age_int, sex_val, uname))
        elif age_int is not None:
            run_execute(cursor, "UPDATE users SET age=? WHERE LOWER(username)=?", (age_int, uname))
        elif sex_val:
            run_execute(cursor, "UPDATE users SET sex=? WHERE LOWER(username)=?", (sex_val, uname))
    run_execute(cursor, "UPDATE users SET onboarding_completed=1 WHERE LOWER(username)=?", (uname,))
    conn.commit()
    conn.close()


@app.route('/api/users/<username>/onboarding/finish', methods=['POST'])
def finish_patient_onboarding(username):
    """Extract profile from interview transcript and mark onboarding complete."""
    uname = _norm(username or "").lower()
    if not uname:
        return jsonify({"error": "Username required"}), 400
    if not OPENAI_AVAILABLE:
        return jsonify({"error": "OpenAI not configured."}), 503
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "OpenAI API key not configured."}), 503

    data = request.get_json() or {}
    history = data.get("conversation_history") or []
    transcript = _format_onboarding_transcript(history)
    if len(transcript) < 40:
        return jsonify({"error": "Please chat with the AI a bit more before saving."}), 400

    conn = get_conn()
    cursor = conn.cursor()
    run_execute(cursor, "SELECT role FROM users WHERE LOWER(username)=?", (uname,))
    row = cursor.fetchone()
    conn.close()
    if not row or _norm(row[0] or "").lower() != "patient":
        return jsonify({"error": "Patient not found"}), 404

    try:
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=_openai_advice_model_id(False),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract structured profile data from a patient welcome interview. "
                        "Reply with JSON only, no markdown, using this shape:\n"
                        '{"likes":"","dislikes":"","religion":"","culture":"",'
                        '"patient_goals":"","food_allergies":"",'
                        '"physical_activity":"","activity_level":"","past_medical_history":"",'
                        '"age":null,"sex":""}\n'
                        "religion: faith or dietary practices they follow (e.g. Muslim, halal; Jewish, kosher; Hindu vegetarian). "
                        "culture: ethnic/cultural background or cuisines important to them. "
                        "Use empty strings for unknown text fields and null for age if not stated."
                    ),
                },
                {"role": "user", "content": transcript[:12000]},
            ],
            max_tokens=600,
            temperature=0.2,
        )
        raw = (completion.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        extracted = json.loads(raw)
        if not isinstance(extracted, dict):
            raise ValueError("Expected JSON object")
        _save_onboarding_profile(uname, extracted)
        return jsonify({"message": "Your intro was saved to your profile.", "onboarding_completed": True})
    except json.JSONDecodeError as e:
        print(f"onboarding extract JSON error: {e}")
        return jsonify({"error": "Could not parse interview. Try a few more answers, then save again."}), 500
    except Exception as e:
        print(f"onboarding finish error: {e}")
        return jsonify({"error": f"Could not save intro: {str(e)}"}), 500


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
    religion = (data.get('religion') or '').strip()
    culture = (data.get('culture') or '').strip()
    notes = data.get('notes', [])
    medical_info = data.get('medical_info', {}) or {}
    conversation_history = data.get('conversation_history', [])
    image = data.get('image')  # optional: data URL (base64) for current message
    role = data.get('role', '')  # 'doctor' = doctor assistant mode
    patient_context = data.get('patient_context', '')  # optional summary when doctor has patient loaded
    # Patient login username: links global + patient-specific PubMed repository into AI context
    context_username = _norm(data.get('context_username') or '').lower()
    acting_username = _norm(data.get('username') or context_username or 'unknown').lower()
    role_norm = _norm(role or '').lower()
    chat_source = 'doctor' if role_norm == 'doctor' else 'patient'
    onboarding_interview = bool(data.get('onboarding_interview'))
    if role_norm == 'doctor':
        onboarding_interview = False
    elif onboarding_interview and _user_onboarding_completed(acting_username):
        onboarding_interview = False

    has_image_flag = bool(image and str(image).startswith('data:image'))
    log_question = question
    if has_image_flag:
        log_question = ((question or '') + ' [image attached]').strip() or '[image attached]'

    if question == ONBOARDING_START_TOKEN:
        question = "Hello! I'm new here and would like a quick welcome chat to get started."
        log_question = "[Welcome interview started]"

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
        
        # Citation rule on every request so follow-up messages also include references
        messages = []
        if role == 'doctor':
            messages.append({"role": "system", "content": AI_CITATION_RULE_DOCTOR})
        else:
            messages.append({"role": "system", "content": AI_CITATION_RULE_PATIENT})

        rating_feedback = _ai_rating_feedback_system_block(acting_username)
        if rating_feedback:
            messages.append({"role": "system", "content": rating_feedback})

        # Welcome interview (new patients) or normal first-message context
        if onboarding_interview:
            messages.append({
                "role": "system",
                "content": AI_PATIENT_ONBOARDING_PROMPT.format(user_name=user_name),
            })
        elif len(conversation_history) == 0:
            if role == 'doctor':
                system_prompt = """You are an AI assistant helping a doctor in their wellbeing practice. Be professional, concise, and accurate. You can answer questions about nutrition, patient care, general health, and wellbeing. If the doctor provides context about a loaded patient, use it to give relevant advice. Do not make up patient data. You must always follow the citation rule from the previous system message."""
                if patient_context:
                    system_prompt += f"\n\nCurrent patient context (if the question is about this patient):\n{patient_context}"
                messages.append({"role": "system", "content": system_prompt})
            else:
                system_prompt = f"""You are a helpful Wellbeing Companion for {user_name}. 
You provide personalized advice about health, recipes, and wellbeing.

User Preferences:
- Likes: {likes if likes else 'Not specified'}
- Dislikes: {dislikes if dislikes else 'Not specified'}
- Religion / faith practices: {religion if religion else 'Not specified'}
- Cultural background: {culture if culture else 'Not specified'}

Important: When suggesting recipes, meals, or any food recommendations, you MUST respect the user's dislikes. Never recommend or suggest any food, ingredient, or meal that appears in their dislikes list. Use their likes when possible to suggest foods they enjoy.
Respect religious and cultural practices they have shared (e.g. halal, kosher, fasting periods, vegetarian norms, traditional cuisines). Do not suggest foods or activities that conflict with their stated religion or culture. When not specified, keep suggestions inclusive.

Doctor-recorded information (use this to personalize advice and avoid conflicting with care plans):
{medical_context}

Recent Doctor Notes:
{notes_context if notes_context else 'No notes available'}

Provide helpful, personalized advice that takes into account the user's preferences and medical context. Be friendly, supportive, and informative. Remember previous parts of the conversation to maintain context. You must always follow the citation rule from the previous system message."""
                messages.append({"role": "system", "content": system_prompt})

        # Curated literature repository (practice-wide + per-patient PMIDs)
        skip_search = bool(image and str(image).startswith('data:image')) or onboarding_interview
        all_repo_pmids = literature_ordered_pmids(context_username)
        repo_pmids = all_repo_pmids
        if rank_pmids_for_question and all_repo_pmids and not skip_search:
            try:
                repo_pmids = rank_pmids_for_question(question, all_repo_pmids, top_k=4)
            except Exception as e:
                print(f'repo pmid rank error: {e}')
                repo_pmids = all_repo_pmids[:4]
        query_pmids = []
        if build_repository_pubmed_block and repo_pmids and not skip_search:
            try:
                repo_block = build_repository_pubmed_block(repo_pmids)
                if repo_block:
                    messages.append({
                        'role': 'system',
                        'content': (
                            'Curated PubMed articles from your literature repository (practice-wide and/or this patient). '
                            'These were pre-filtered for relevance to the user question—still verify each excerpt before citing. '
                            'In **Supporting references**, include markdown links only for articles you actually used.\n\n'
                            + repo_block
                        ),
                    })
            except Exception as e:
                print(f'Literature repository block error: {e}')

        # PubMed (NLM) + openFDA: open public clinical text (no vendor key required)
        use_open_sources = os.environ.get('AI_OPEN_SOURCES', '1').strip().lower() not in ('0', 'false', 'no', 'off')
        if gather_open_source_clinical_bundle and use_open_sources and not skip_search:
            try:
                bundle = gather_open_source_clinical_bundle(question)
                os_clinical = bundle.get('text_block')
                query_pmids = bundle.get('query_pmids') or []
                if os_clinical:
                    messages.append({
                        'role': 'system',
                        'content': (
                            'The following excerpts come from open public data: PubMed (NLM) and/or openFDA (FDA). '
                            'Use ONLY excerpts that directly answer the user question—skip the rest. '
                            'In **Supporting references**, link only sources you relied on, using PubMed "URL:" lines below. '
                            'Do not invent PMIDs or links.\n\n'
                            + os_clinical
                        ),
                    })
            except Exception as e:
                print(f'Open clinical sources error: {e}')

        # Optional live web search (Tavily): inject real pages + URLs for this question
        if not skip_search and os.environ.get('TAVILY_API_KEY'):
            web_block = tavily_web_search(question)
            if web_block:
                messages.append({
                    'role': 'system',
                    'content': (
                        'Live web search for the user\'s latest question. '
                        'Read each snippet—cite ONLY results that clearly relate to the question. '
                        'In **Supporting references**, use markdown [title](url) with URLs from "URL:" lines below.\n\n'
                        + web_block
                    ),
                })
        
        # Add conversation history (user messages may include image - use content array for vision)
        for msg in conversation_history:
            if msg.get('role') not in ['user', 'assistant']:
                continue
            hist_role = msg['role']
            content = msg.get('content', '')
            img = msg.get('image')
            if hist_role == 'user' and img and str(img).startswith('data:image'):
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": content or "(Image attached)"},
                        {"type": "image_url", "image_url": {"url": img}}
                    ]
                })
            else:
                messages.append({"role": hist_role, "content": content or ""})
        
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
        model = _openai_advice_model_id(has_image)
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=950,
            temperature=0.35
        )
        
        response_text = completion.choices[0].message.content

        all_pmids = []
        seen_p = set()
        for p in repo_pmids + query_pmids:
            ps = str(p).strip()
            if ps.isdigit() and ps not in seen_p:
                seen_p.add(ps)
                all_pmids.append(ps)
        references = []
        if pubmed_references_for_pmids and all_pmids:
            try:
                candidate_refs = pubmed_references_for_pmids(all_pmids)
                if filter_pubmed_references_cited_in_response:
                    references = filter_pubmed_references_cited_in_response(
                        response_text, candidate_refs
                    )
                else:
                    references = candidate_refs
            except Exception as e:
                print(f'pubmed_references_for_pmids error: {e}')

        log_id = _insert_ai_chat_log(
            username=acting_username,
            display_name=_norm(user_name or ''),
            role=role_norm or chat_source,
            context_username=context_username,
            source=chat_source,
            question=log_question,
            response=response_text,
            references=references,
            model=model,
            success=True,
            had_image=has_image_flag,
        )

        return jsonify({"response": response_text, "references": references, "log_id": log_id})

    except Exception as e:
        err_msg = str(e)
        print(f"OpenAI API error: {err_msg}")
        _insert_ai_chat_log(
            username=acting_username,
            display_name=_norm(user_name or ''),
            role=role_norm or chat_source,
            context_username=context_username,
            source=chat_source,
            question=log_question,
            response=None,
            references=None,
            model=locals().get('model', ''),
            success=False,
            error_message=err_msg,
            had_image=has_image_flag,
        )
        return jsonify({"error": f"AI service error: {err_msg}"}), 500


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
    conn = get_conn()
    cursor = conn.cursor()
    try:
        if patient_id and not username:
            run_execute(cursor,"SELECT username FROM users WHERE patient_id=?", (patient_id,))
            row = cursor.fetchone()
            username = (row[0] or '').strip() if row else ''
        if not username:
            conn.close()
            return jsonify({"error": "Patient not found"}), 404
        uname_lower = username.lower()
        run_execute(cursor,
            "SELECT name, age, sex FROM users WHERE username=?", (uname_lower,)
        )
        user_row = cursor.fetchone()
        user_name = user_row[0] if user_row else username
        user_age = user_row[1] if user_row and len(user_row) > 1 else None
        user_sex = user_row[2] if user_row and len(user_row) > 2 else ""
        run_execute(cursor,
            "SELECT likes, dislikes, religion, culture FROM preferences WHERE username=?", (uname_lower,)
        )
        prefs_row = cursor.fetchone()
        likes = (prefs_row[0] or "") if prefs_row else ""
        dislikes = (prefs_row[1] or "") if prefs_row and len(prefs_row) > 1 else ""
        religion = (prefs_row[2] or "") if prefs_row and len(prefs_row) > 2 else ""
        culture = (prefs_row[3] or "") if prefs_row and len(prefs_row) > 3 else ""
        run_execute(cursor,
            "SELECT note, created_at FROM notes WHERE LOWER(username)=? ORDER BY created_at DESC LIMIT 5",
            (uname_lower,)
        )
        notes_rows = cursor.fetchall()
        notes_txt = "\n".join([n[0] or "" for n in notes_rows]) if notes_rows else ""
        try:
            run_execute(cursor,
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
            f"Religion / faith practices: {religion or 'None'}",
            f"Cultural background: {culture or 'None'}",
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

        web_extra = ""
        if os.environ.get('TAVILY_API_KEY') and os.environ.get('AI_WEB_SEARCH', '1').strip().lower() not in ('0', 'false', 'no', 'off'):
            qparts = ['nutrition dietary guidelines healthy eating']
            if med[9]:
                qparts.append(str(med[9]))
            if med[10]:
                qparts.append(str(med[10]))
            if med[2]:
                qparts.append(str(med[2]))
            wb = tavily_web_search(' '.join(qparts)[:500], max_results=5)
            if wb:
                web_extra = '\n\n' + wb + '\n\n(If you use information from the web block above, the references string must include the exact https URLs from the URL: lines.)'

        w_kg = _nutrition_weight_kg(med[6])
        h_cm = _nutrition_height_cm(med[5], med[7], med[8])
        maint_est, est_notes = _nutrition_maintenance_estimate(
            w_kg, h_cm, user_age, user_sex, med[11], med[3]
        )
        calibration = ""
        if maint_est:
            calibration = (
                f"\n\nEnergy targets (follow closely when height/weight/age align with context): "
                f"estimated maintenance TDEE ≈ {maint_est} kcal/day (Mifflin-St Jeor BMR × activity factor). "
                f"Set maintenance_calories within about ±10% of that estimate. "
                f"Set weight_loss_calories about 400–500 kcal/day below maintenance_calories "
                f"unless contraindicated in notes—never equal to or above maintenance. "
                f"Minimum safe intake for weight-loss phase is approximately 1200 kcal/day (many women) "
                f"or 1500 kcal/day (many men)—do not go lower for adults unless clinician notes explicitly allow."
            )

        prompt = f"""Generate a personalized nutrition plan for this patient. Use ONLY the information below. Return a JSON object with exactly these keys (all strings; for arrays use JSON arrays of strings):

- maintenance_calories: e.g. "2000"
- weight_loss_calories: e.g. "1500" (must be MEANINGFULLY LESS than maintenance_calories—prefer at least ~300–500 kcal lower)
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
- references: string with 3–6 items: if web search results appear below, include exact https URLs from those results plus named guidelines; otherwise named sources only (no invented URLs).

Patient context:
{context}
{web_extra}
{calibration}

Consistency: weight_loss_calories must stay below maintenance_calories. Avoid extreme starvation-level numbers for adults (e.g. do not recommend sustained intake under ~1200 kcal/day for typical adult females or ~1500 for typical adult males without explicit clinician instruction in the context above).

Return only valid JSON, no other text. CRITICAL: Do not suggest or include ANY food from the patient's "Dislikes" list anywhere in the plan—not in meals, foods_include, or grocery lists. Use their likes when suggesting foods they might enjoy. Respect religious and cultural practices in Religion/Cultural background fields (e.g. halal, kosher, fasting, traditional cuisines). foods_avoid = medically relevant only (allergies, conditions, drug interactions)."""

        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=_openai_nutrition_model_id(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.35,
            response_format={"type": "json_object"}
        )
        raw = completion.choices[0].message.content or "{}"
        validation_notes = list(est_notes or [])
        try:
            plan_data = json.loads(raw)
        except Exception:
            plan_data = {"_raw": raw}

        if isinstance(plan_data, dict) and "_raw" not in plan_data:
            plan_data, vnotes = _nutrition_clamp_plan(
                plan_data, maint_est, user_sex, user_age
            )
            validation_notes.extend(vnotes)

        return jsonify({"plan": plan_data, "validation_notes": validation_notes})
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"Nutrition plan error: {e}")
        return jsonify({"error": str(e)}), 500


# Serve frontend (for all-in-one deployment)
@app.route("/console/<secret>/")
@app.route("/console/<secret>")
def admin_console(secret):
    """Private feedback admin login when ADMIN_ACCESS_SECRET is set. Share this URL, not /admin.html."""
    if not _admin_access_secret():
        return _admin_console_help_response("no_env")
    if not _console_secret_ok(secret):
        return _admin_console_help_response("bad_secret")
    return send_from_directory(BASE_DIR, "admin.html")


@app.route("/console/<secret>/create/")
@app.route("/console/<secret>/create")
def admin_console_setup(secret):
    """Create Admin accounts (bootstrap key) — only when ADMIN_ACCESS_SECRET matches URL."""
    if not _admin_access_secret():
        return _admin_console_help_response("no_env")
    if not _console_secret_ok(secret):
        return _admin_console_help_response("bad_secret")
    return send_from_directory(BASE_DIR, "admin-setup.html")


@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route("/manifest.webmanifest")
def serve_pwa_manifest():
    """PWA manifest (installable app alongside the normal website)."""
    return send_from_directory(
        BASE_DIR, "manifest.webmanifest", mimetype="application/manifest+json"
    )


@app.route("/sw.js")
def serve_service_worker():
    """Service worker; scope / so it applies to /api and static assets."""
    resp = send_from_directory(BASE_DIR, "sw.js")
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.route('/<path:filename>')
def serve_static(filename):
    if filename == "admin.html" and _admin_access_secret():
        return "", 404
    if filename == "admin-setup.html":
        if _admin_access_secret():
            return "", 404
        return send_from_directory(BASE_DIR, "admin-setup.html")
    if filename in ALLOWED_STATIC:
        resp = send_from_directory(BASE_DIR, filename)
        if filename in ('app.js', 'styles.css', 'api-service.js', 'index.html'):
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
        return resp
    return '', 404


# Initialize database when app is loaded (needed when running under gunicorn on Render)
_maybe_migrate_legacy_sqlite()
init_db()
if USE_PG:
    print("Database: PostgreSQL (DATABASE_URL) — user data persists with the hosted database.")
else:
    _abs_sqlite = os.path.abspath(SQLITE_DATABASE_PATH)
    print(f"Database: SQLite file at {_abs_sqlite}")
    if _sqlite_likely_ephemeral_host():
        print("If accounts disappear after each deploy, use PostgreSQL (DATABASE_URL) or a persistent disk + SQLITE_DATABASE_PATH.")

if _admin_access_secret():
    print(
        "Admin feedback console: private URL path /console/<ADMIN_ACCESS_SECRET>/ "
        "(env ADMIN_ACCESS_SECRET). Admin creation: /console/<secret>/create/ with ADMIN_BOOTSTRAP_KEY."
    )
elif _admin_bootstrap_key():
    print(
        "ADMIN_BOOTSTRAP_KEY is set: open /admin-setup.html to create Admin users, "
        "or set ADMIN_ACCESS_SECRET to use only /console/<secret>/ and /console/<secret>/create/."
    )

if __name__ == '__main__':
    if '--email-feedback-backlog' in sys.argv:
        try:
            n = run_email_feedback_backlog_digest()
            if n == 0:
                print("No feedback rows in the database; no email sent.")
            else:
                print(f"Sent one digest email covering {n} feedback row(s) to FEEDBACK_EMAIL_TO.")
        except Exception as ex:
            print(f"Failed: {ex}")
            sys.exit(1)
        sys.exit(0)

    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print("=" * 50)
    print("Wellbeing Companion Backend Server")
    print("=" * 50)
    print(f"Database: PostgreSQL" if USE_PG else f"Database: SQLite ({os.path.abspath(SQLITE_DATABASE_PATH)})")
    print(f"Server starting on http://0.0.0.0:{port}")
    print(f"API Base URL: http://0.0.0.0:{port}/api")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=debug)


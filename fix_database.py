#!/usr/bin/env python3
"""Fix database - Add patient_id column if missing"""
import sqlite3

DB_NAME = "wellbeing.db"

print("Fixing database...")
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Check if patient_id column exists
cursor.execute("PRAGMA table_info(users)")
columns = [col[1] for col in cursor.fetchall()]

if 'patient_id' not in columns:
    print("Adding patient_id column...")
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN patient_id TEXT")
        conn.commit()
        print("✓ patient_id column added")
    except Exception as e:
        print(f"Error adding column: {e}")
else:
    print("✓ patient_id column already exists")

# Create unique index for patient_id
try:
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_patient_id_unique ON users(patient_id) WHERE patient_id IS NOT NULL")
    conn.commit()
    print("✓ Unique index created")
except Exception as e:
    print(f"Note: {e}")

# Check current patients
cursor.execute("SELECT username, role, patient_id FROM users WHERE role='Patient'")
patients = cursor.fetchall()

print(f"\nFound {len(patients)} patient(s):")
for patient in patients:
    print(f"  {patient[0]}: Patient ID = {patient[2] or 'NONE'}")

conn.close()
print("\nDatabase fix complete! Now restart your server: python server.py")


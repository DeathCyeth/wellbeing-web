import sqlite3

DB_NAME = "wellbeing.db"

# Check database
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Check patients
cursor.execute("SELECT username, role, patient_id FROM users WHERE role='Patient'")
patients = cursor.fetchall()

print("Current Patients:")
for patient in patients:
    print(f"  Username: {patient[0]}, Role: {patient[1]}, Patient ID: {patient[2] or 'NONE'}")

# Check if patient_id column exists
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print("\nUsers table columns:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()


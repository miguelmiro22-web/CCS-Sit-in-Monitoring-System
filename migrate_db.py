import sqlite3

conn = sqlite3.connect('ccs.db')
c = conn.cursor()

try:
    c.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
    print("✅ Added points column")
except sqlite3.OperationalError as e:
    print(f"⚠️ points column may already exist: {e}")

try:
    c.execute("ALTER TABLE users ADD COLUMN converted_sessions INTEGER DEFAULT 0")
    print("✅ Added converted_sessions column")
except sqlite3.OperationalError as e:
    print(f"⚠️ converted_sessions column may already exist: {e}")

c.execute('''
    CREATE TABLE IF NOT EXISTS point_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        points INTEGER NOT NULL,
        action TEXT NOT NULL,
        remarks TEXT,
        date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
print("✅ Created point_logs table")

conn.commit()
conn.close()
print("\n🎉 Migration completed. Restart Flask.")
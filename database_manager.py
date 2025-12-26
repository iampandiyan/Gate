import sqlite3
import hashlib
from datetime import datetime
import os

DB_NAME = "smartgate.db"

def init_db():
    """Initialize the database tables and default users."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. USERS TABLE
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'guard',
                    full_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT
                )''')
    
    # 2. AUDIT LOGS
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    username TEXT,
                    action TEXT,
                    details TEXT
                )''')

    # 3. RESIDENTS (Allow List)
    c.execute('''CREATE TABLE IF NOT EXISTS residents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_number TEXT UNIQUE,
                    owner_name TEXT,
                    flat_number TEXT,
                    phone_number TEXT
                )''')

    # 4. ENTRY LOGS (History)
    c.execute('''CREATE TABLE IF NOT EXISTS entry_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_number TEXT,
                    entry_time TEXT,
                    exit_time TEXT,
                    gate_name TEXT,
                    image_path TEXT,
                    status TEXT DEFAULT 'INSIDE' 
                )''')

    # --- SEED USERS ---
    
    # A. Default Admin (admin / admin123)
    admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)", 
                  ('admin', admin_pass, 'admin', 'Building Manager'))
    except sqlite3.IntegrityError: pass 

    # B. Technician User (tech_support / Support@2025!)
    tech_pass = hashlib.sha256("Support@2025!".encode()).hexdigest() 
    try:
        c.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)", 
                  ('tech_support', tech_pass, 'tech', 'System Technician'))
        print("✅ Technician User Created")
    except sqlite3.IntegrityError: pass

    conn.commit()
    conn.close()

def check_login(username, password):
    """Verify credentials."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    hashed_input = hashlib.sha256(password.encode()).hexdigest()
    
    c.execute("SELECT role FROM users WHERE username=? AND password_hash=?", (username, hashed_input))
    result = c.fetchone()
    conn.close()
    
    if result:
        log_audit(username, "LOGIN", "User logged in successfully")
        return True, result[0] # Returns (True, 'admin')
    else:
        log_audit(username, "LOGIN_FAILED", "Invalid password attempt")
        return False, None

def change_password(username, old_pass, new_pass, is_technician_reset=False):
    """Change password logic."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Check Old Password (unless tech override)
    if not is_technician_reset:
        hashed_old = hashlib.sha256(old_pass.encode()).hexdigest()
        c.execute("SELECT 1 FROM users WHERE username=? AND password_hash=?", (username, hashed_old))
        if not c.fetchone():
            conn.close()
            return False, "❌ Incorrect Old Password"

    # 2. Update
    hashed_new = hashlib.sha256(new_pass.encode()).hexdigest()
    c.execute("UPDATE users SET password_hash=? WHERE username=?", (hashed_new, username))
    
    conn.commit()
    conn.close()
    
    action = "PASS_RESET_ADMIN" if is_technician_reset else "PASS_CHANGE_SELF"
    log_audit(username, action, "Password updated successfully")
    return True, "✅ Password Changed Successfully"

def log_audit(username, action, details):
    """Record an event."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO audit_logs (timestamp, username, action, details) VALUES (?, ?, ?, ?)",
              (timestamp, username, action, details))
    conn.commit()
    conn.close()

def get_resident_by_plate(plate_text):
    """Returns resident info if exists, else None"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT owner_name, flat_number, phone_number FROM residents WHERE plate_number=?", (plate_text,))
    result = c.fetchone()
    conn.close()
    return result # Returns (name, flat, phone) or None

def add_new_resident(plate, name, flat, phone):
    """Adds a new car to the database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO residents (plate_number, owner_name, flat_number, phone_number) VALUES (?, ?, ?, ?)",
                  (plate, name, flat, phone))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Plate already exists
    finally:
        conn.close()

def log_entry_event(plate, gate, image_path, status="INSIDE"):
    """Logs the entry into history"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO entry_logs (plate_number, entry_time, gate_name, image_path, status) VALUES (?, ?, ?, ?, ?)",
              (plate, now, gate, image_path, status))
    conn.commit()
    conn.close()

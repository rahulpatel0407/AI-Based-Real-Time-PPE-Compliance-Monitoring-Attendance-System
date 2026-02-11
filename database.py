import sqlite3
import os
from datetime import datetime

DB_PATH = "attendance.db"

def init_db():
    """Initialize SQLite database with tables for attendance system."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Employees table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            employee_id TEXT NOT NULL UNIQUE,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Face embeddings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS face_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL UNIQUE,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')
    
    # Attendance records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            check_in TIMESTAMP,
            check_out TIMESTAMP,
            date DATE,
            status TEXT DEFAULT 'Present',
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')

    # Cameras table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            stream_url TEXT,
            snapshot_url TEXT,
            encrypted_credentials TEXT,
            status TEXT DEFAULT 'Offline',
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def add_camera(name, camera_type, stream_url, snapshot_url, encrypted_credentials, status, created_by, location=None):
    """Add a new camera configuration."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO cameras (name, type, stream_url, snapshot_url, encrypted_credentials, status, location, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, camera_type, stream_url, snapshot_url, encrypted_credentials, status, location, created_by))
    conn.commit()
    camera_id = cursor.lastrowid
    conn.close()
    return camera_id

def update_camera_status(camera_id, status):
    """Update the status of a camera."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE cameras SET status = ? WHERE id = ?', (status, camera_id))
    conn.commit()
    conn.close()

def get_cameras():
    """Retrieve all camera configurations."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, type, stream_url, snapshot_url, encrypted_credentials, status, location, created_at, created_by
        FROM cameras
        ORDER BY created_at DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_camera_by_id(camera_id):
    """Retrieve a single camera configuration by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, type, stream_url, snapshot_url, encrypted_credentials, status, location, created_at, created_by
        FROM cameras
        WHERE id = ?
    ''', (camera_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def delete_camera(camera_id):
    """Delete a camera configuration."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cameras WHERE id = ?', (camera_id,))
    conn.commit()
    conn.close()

def add_employee(name, employee_id, email=None):
    """Add a new employee to the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO employees (name, employee_id, email) VALUES (?, ?, ?)',
            (name, employee_id, email)
        )
        conn.commit()
        employee_pk = cursor.lastrowid
        conn.close()
        return employee_pk
    except sqlite3.IntegrityError as e:
        return None

def store_face_embedding(employee_id, embedding):
    """Store face embedding as BLOB."""
    import numpy as np
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Convert numpy array to binary
    embedding_blob = embedding.tobytes()
    
    cursor.execute('''
        INSERT OR REPLACE INTO face_embeddings (employee_id, embedding)
        VALUES (?, ?)
    ''', (employee_id, embedding_blob))
    
    conn.commit()
    conn.close()

def get_face_embedding(employee_id):
    """Retrieve face embedding for an employee."""
    import numpy as np
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT embedding FROM face_embeddings WHERE employee_id = ?', (employee_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        embedding_blob = result[0]
        # Convert binary back to numpy array
        embedding = np.frombuffer(embedding_blob, dtype=np.float64)
        return embedding
    return None

def get_all_face_embeddings():
    """Retrieve all face embeddings with employee info."""
    import numpy as np
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT e.id, e.name, fe.embedding
        FROM employees e
        JOIN face_embeddings fe ON e.id = fe.employee_id
    ''')
    results = cursor.fetchall()
    conn.close()
    
    embeddings_data = []
    for emp_id, name, embedding_blob in results:
        embedding = np.frombuffer(embedding_blob, dtype=np.float64)
        embeddings_data.append((emp_id, name, embedding))
    
    return embeddings_data

def mark_attendance(employee_id, check_in=True):
    """Mark check-in or check-out for an employee."""
    from datetime import datetime
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().date()
    current_time = datetime.now()
    
    # Check if record exists for today
    cursor.execute(
        'SELECT id FROM attendance WHERE employee_id = ? AND date = ?',
        (employee_id, today)
    )
    record = cursor.fetchone()
    
    if record:
        if check_in:
            # Update check_in if not already set
            cursor.execute(
                'UPDATE attendance SET check_in = ? WHERE id = ? AND check_in IS NULL',
                (current_time, record[0])
            )
        else:
            # Update check_out
            cursor.execute(
                'UPDATE attendance SET check_out = ? WHERE id = ?',
                (current_time, record[0])
            )
    else:
        if check_in:
            cursor.execute('''
                INSERT INTO attendance (employee_id, check_in, date, status)
                VALUES (?, ?, ?, 'Present')
            ''', (employee_id, current_time, today))
    
    conn.commit()
    conn.close()

def get_employee_by_id(employee_id):
    """Get employee details by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, employee_id FROM employees WHERE id = ?', (employee_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_all_employees():
    """Get all employees."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, employee_id FROM employees')
    results = cursor.fetchall()
    conn.close()
    return results

def get_attendance_report(start_date=None, end_date=None):
    """Get attendance report for a date range."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if start_date and end_date:
        cursor.execute('''
            SELECT e.name, e.employee_id, a.date, a.check_in, a.check_out, a.status
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.date BETWEEN ? AND ?
            ORDER BY a.date DESC, e.name
        ''', (start_date, end_date))
    else:
        cursor.execute('''
            SELECT e.name, e.employee_id, a.date, a.check_in, a.check_out, a.status
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            ORDER BY a.date DESC, e.name
        ''')
    
    results = cursor.fetchall()
    conn.close()
    return results

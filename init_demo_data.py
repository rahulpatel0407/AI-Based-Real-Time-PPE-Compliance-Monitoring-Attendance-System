#!/usr/bin/env python3
"""
Database initialization script with demo data for IOCL Safety System
"""

import sqlite3
from datetime import datetime, timedelta
from database import (
    init_db, add_employee, mark_attendance,
    get_all_employees, DB_PATH
)

def populate_demo_data():
    """Populate database with demo employees and attendance records"""
    
    # Initialize database
    init_db()
    print("[INFO] Database initialized")
    
    # Demo employees
    demo_employees = [
        ("Raj Kumar", "EMP001", "raj.kumar@iocl.com"),
        ("Priya Singh", "EMP002", "priya.singh@iocl.com"),
        ("Anil Verma", "EMP003", "anil.verma@iocl.com"),
        ("Neha Sharma", "EMP004", "neha.sharma@iocl.com"),
        ("Suresh Patel", "EMP005", "suresh.patel@iocl.com"),
        ("Vikram Kumar", "EMP006", "vikram.kumar@iocl.com"),
        ("Anjali Desai", "EMP007", "anjali.desai@iocl.com"),
        ("Ramesh Singh", "EMP008", "ramesh.singh@iocl.com"),
        ("Meera Nair", "EMP009", "meera.nair@iocl.com"),
        ("Deepak Sharma", "EMP010", "deepak.sharma@iocl.com"),
    ]
    
    # Add employees
    employee_ids = []
    for name, emp_id, email in demo_employees:
        emp_id_pk = add_employee(name, emp_id, email)
        if emp_id_pk:
            employee_ids.append(emp_id_pk)
            print(f"[OK] Added employee: {name} ({emp_id})")
        else:
            print(f"[SKIP] Employee already exists: {name}")
            # Get existing employee ID
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM employees WHERE employee_id = ?', (emp_id,))
            result = cursor.fetchone()
            conn.close()
            if result:
                employee_ids.append(result[0])
    
    # Add attendance records for today and past 6 days
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now()
    for day_offset in range(7):  # 7 days of attendance
        current_date = today - timedelta(days=day_offset)
        date_str = current_date.date()
        
        for i, emp_id_pk in enumerate(employee_ids):
            # Random check-in times between 7:00 AM and 9:00 AM
            if i % 10 != 0:  # 90% present
                check_in_hour = 7 + (i % 2)  # 7 or 8 AM
                check_in_minute = (i * 7) % 60  # Vary minutes
                check_in = current_date.replace(hour=check_in_hour, minute=check_in_minute, second=0)
                
                # Check-out times between 4:00 PM and 6:00 PM
                check_out_hour = 16 + (i % 2)  # 4 or 5 PM
                check_out_minute = (i * 13) % 60
                check_out = current_date.replace(hour=check_out_hour, minute=check_out_minute, second=0)
                
                # Insert or update attendance record
                cursor.execute('''
                    SELECT id FROM attendance 
                    WHERE employee_id = ? AND date = ?
                ''', (emp_id_pk, date_str))
                
                result = cursor.fetchone()
                if result:
                    # Update existing record
                    cursor.execute('''
                        UPDATE attendance 
                        SET check_in = ?, check_out = ?, status = 'Present'
                        WHERE id = ?
                    ''', (check_in, check_out, result[0]))
                else:
                    # Insert new record
                    cursor.execute('''
                        INSERT INTO attendance (employee_id, check_in, check_out, date, status)
                        VALUES (?, ?, ?, ?, 'Present')
                    ''', (emp_id_pk, check_in, check_out, date_str))
            else:
                # Mark as absent (no check-in)
                cursor.execute('''
                    SELECT id FROM attendance 
                    WHERE employee_id = ? AND date = ?
                ''', (emp_id_pk, date_str))
                
                result = cursor.fetchone()
                if not result:
                    cursor.execute('''
                        INSERT INTO attendance (employee_id, date, status)
                        VALUES (?, ?, 'Absent')
                    ''', (emp_id_pk, date_str))
    
    conn.commit()
    conn.close()
    print(f"\n[OK] Added attendance records for {len(employee_ids)} employees")
    
    # Verify data
    print("\n[INFO] Verifying data...")
    employees = get_all_employees()
    print(f"[OK] Total employees in database: {len(employees)}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM attendance')
    attendance_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM attendance WHERE status = "Present"')
    present_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"[OK] Total attendance records: {attendance_count}")
    print(f"[OK] Present records: {present_count}")
    print(f"[OK] Absent records: {attendance_count - present_count}")
    
    print("\n✓ Database populated with demo data!")

if __name__ == '__main__':
    populate_demo_data()

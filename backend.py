from flask import Flask, jsonify, request, send_from_directory, session, redirect, Response, send_file
from flask_cors import CORS
from functools import wraps
import sqlite3
import json
from datetime import datetime
import os
import secrets
import imghdr
import logging
import base64
import ipaddress
import socket
import time
import uuid
from typing import Optional
from urllib.parse import urlparse
import requests
import io
import cv2
import numpy as np
from pathlib import Path
from fire_alarm import start_fire_alarm, stop_fire_alarm, is_alarm_active
from threading import Lock, Thread, Event
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet, InvalidToken
from database import (
    get_all_employees, get_attendance_report,
    get_employee_by_id, init_db, add_camera, get_cameras, get_camera_by_id,
    delete_camera
)
from violation_recorder import ViolationRecorder
from violation_logic import is_helmet_violation
from ppe_color_utils import (
    build_color_mask,
    refine_mask,
    color_coverage,
    thresholds_from_cfg,
    load_calibration,
)

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)

# Uploads directory for profile avatars
AVATAR_DIR = os.path.join(app.static_folder, 'uploads', 'profiles')
os.makedirs(AVATAR_DIR, exist_ok=True)
MAX_AVATAR_SIZE = 2 * 1024 * 1024

# Set secret key for session management
# SECURITY: Use environment variable, generate random key for each startup in dev
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if os.environ.get('FLASK_ENV') == 'production':
        raise ValueError('SECRET_KEY environment variable must be set in production')
    # Generate random key for development only
    SECRET_KEY = secrets.token_urlsafe(32)
    print('[WARNING] Using randomly generated SECRET_KEY for development. Set SECRET_KEY environment variable for production.')

app.secret_key = SECRET_KEY

# ==================== Camera Security & Logging ====================
LOG_DIR = os.path.join(os.getcwd(), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

CAMERA_LOGGER = logging.getLogger('camera_actions')
if not CAMERA_LOGGER.handlers:
    camera_log_path = os.path.join(LOG_DIR, 'camera_actions.log')
    handler = logging.FileHandler(camera_log_path)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    handler.setFormatter(formatter)
    CAMERA_LOGGER.addHandler(handler)
    CAMERA_LOGGER.setLevel(logging.INFO)

VIOLATION_API_LOGGER = logging.getLogger('violation_api')
if not VIOLATION_API_LOGGER.handlers:
    violation_log_path = os.path.join(LOG_DIR, 'violation_api.log')
    handler = logging.FileHandler(violation_log_path)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    handler.setFormatter(formatter)
    VIOLATION_API_LOGGER.addHandler(handler)
    VIOLATION_API_LOGGER.setLevel(logging.INFO)

CAMERA_PREVIEW_MAX_BYTES = 2 * 1024 * 1024

def get_camera_fernet():
    """Return Fernet instance for encrypting camera credentials."""
    key = os.environ.get('CAMERA_CRED_KEY')
    if not key:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError('CAMERA_CRED_KEY environment variable must be set in production')
        key = Fernet.generate_key().decode('utf-8')
        print('[WARNING] Using randomly generated CAMERA_CRED_KEY for development. Set CAMERA_CRED_KEY environment variable for production.')

    if isinstance(key, str):
        key = key.encode('utf-8')
    return Fernet(key)

def encrypt_camera_credentials(username, password):
    """Encrypt camera credentials for storage."""
    if not username and not password:
        return None
    payload = json.dumps({'username': username, 'password': password})
    fernet = get_camera_fernet()
    return fernet.encrypt(payload.encode('utf-8')).decode('utf-8')

def decrypt_camera_credentials(encrypted_payload):
    """Decrypt camera credentials for internal use."""
    if not encrypted_payload:
        return {'username': None, 'password': None}
    try:
        fernet = get_camera_fernet()
        decoded = fernet.decrypt(encrypted_payload.encode('utf-8')).decode('utf-8')
        return json.loads(decoded)
    except (InvalidToken, ValueError, json.JSONDecodeError):
        return {'username': None, 'password': None}

def log_camera_action(action, camera_id, camera_name):
    """Log camera add/delete actions without sensitive data."""
    username = session.get('user_id', 'unknown')
    CAMERA_LOGGER.info('%s | camera_id=%s | camera_name=%s | user=%s', action, camera_id, camera_name, username)

# Initialize database
init_db()

# ==================== User Credentials (Simple Authentication) ====================
# In production, use proper database with hashed passwords
VALID_USERS = {
    'admin': {
        'password': 'admin123',
        'role': 'admin',
        'name': 'Administrator',
        'email': 'admin@iocl.com',
        'employee_id': 'EMP0001',
        'department': 'Safety',
        'avatar_url': '',
        'last_login': ''
    },
    'user': {
        'password': 'user123',
        'role': 'staff',
        'name': 'Authorized Staff',
        'email': 'user@iocl.com',
        'employee_id': 'EMP0002',
        'department': 'Operations',
        'avatar_url': '',
        'last_login': ''
    }
}

# ==================== Authentication Decorator ====================
def login_required(f):
    """Decorator to check if user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for valid token or session
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token and 'user_id' not in session:
            return jsonify({'error': 'Unauthorized', 'message': 'Please log in first'}), 401
        
        # Verify token (basic implementation)
        if token:
            # In production, verify JWT token here
            pass
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to ensure user has admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({'error': 'Forbidden', 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    """Decorator to ensure user has one of the allowed roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            role = session.get('role')
            if role not in roles:
                return jsonify({'error': 'Forbidden', 'message': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def is_private_address(ip_str):
    """Check if IP address is private or otherwise unsafe for SSRF."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        )
    except ValueError:
        return True

def validate_safe_url(url, allowed_schemes):
    """Validate URLs and protect against SSRF attacks."""
    if not url or len(url) > 2048:
        return False, 'Invalid URL length'

    parsed = urlparse(url)
    if parsed.scheme.lower() not in allowed_schemes:
        return False, 'Unsupported URL scheme'

    if not parsed.hostname:
        return False, 'URL must include a hostname'

    if parsed.username or parsed.password:
        return False, 'Credentials must be provided separately'

    hostname = parsed.hostname
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for info in addr_info:
            ip = info[4][0]
            if is_private_address(ip):
                return False, 'Private or unsafe address is not allowed'
    except socket.gaierror:
        return False, 'Unable to resolve host'

    return True, None

def apply_credentials_to_url(url, username, password):
    """Inject credentials into a URL for RTSP streams when needed."""
    if not username or not password:
        return url

    parsed = urlparse(url)
    if parsed.username or parsed.password:
        return url

    netloc = f"{username}:{password}@{parsed.hostname}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()

# ==================== Authentication Routes ====================

@app.route('/api/login', methods=['POST'])
def login():
    """User login endpoint with validation"""
    try:
        data = request.get_json()
        username = data.get('employeeId', '').strip() or data.get('username', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        # Input validation
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Username and password are required'
            }), 400
        
        # Length validation to prevent DoS
        if len(username) > 50 or len(password) > 100:
            return jsonify({
                'success': False,
                'message': 'Invalid username or password format'
            }), 400
        
        # Alphanumeric username validation
        if not username.replace('_', '').replace('-', '').isalnum():
            return jsonify({
                'success': False,
                'message': 'Invalid username format'
            }), 400
        
        # Check credentials (case-sensitive)
        if username not in VALID_USERS:
            # Generic message to prevent username enumeration
            return jsonify({
                'success': False,
                'message': 'Invalid username or password'
            }), 401
        
        user = VALID_USERS[username]
        
        # Use constant-time comparison to prevent timing attacks
        import hmac
        if not hmac.compare_digest(user['password'], password):
            return jsonify({
                'success': False,
                'message': 'Invalid username or password'
            }), 401
        
        # Create session
        session['user_id'] = username
        session['role'] = user['role']
        session['name'] = user['name']
        session['employee_id'] = user.get('employee_id', '')
        session['department'] = user.get('department', '')
        session['avatar_url'] = user.get('avatar_url', '')
        session.permanent = remember  # Set persistent session if remember checked

        # Track last login
        user['last_login'] = datetime.now().strftime('%d-%m-%Y %H:%M')
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {
                'username': username,
                'name': user['name'],
                'email': user['email'],
                'role': user['role'],
                'employeeId': user.get('employee_id', ''),
                'department': user.get('department', ''),
                'lastLogin': user.get('last_login', ''),
                'avatarUrl': user.get('avatar_url', '')
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Login error: {e}")
        return jsonify({
            'success': False,
            'message': 'Login error occurred'
        }), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """User logout endpoint"""
    try:
        session.clear()
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Logout error: {str(e)}'
        }), 500

@app.route('/api/auth/verify', methods=['GET'])
def verify_auth():
    """Verify if user is authenticated"""
    if 'user_id' in session:
        user = VALID_USERS.get(session['user_id'])
        if user:
            return jsonify({
                'authenticated': True,
                'user': {
                    'username': session['user_id'],
                    'name': session.get('name'),
                    'role': session.get('role'),
                    'employeeId': session.get('employee_id', ''),
                    'department': session.get('department', ''),
                    'lastLogin': user.get('last_login', ''),
                    'avatarUrl': session.get('avatar_url', '')
                }
            }), 200
    
    return jsonify({
        'authenticated': False
    }), 401

@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    """Get current user profile"""
    username = session.get('user_id')
    if not username or username not in VALID_USERS:
        return jsonify({'error': 'User not found'}), 404
    
    user = VALID_USERS[username]
    return jsonify({
        'user': {
            'username': username,
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'employeeId': user.get('employee_id', ''),
            'department': user.get('department', ''),
            'lastLogin': user.get('last_login', ''),
            'avatarUrl': user.get('avatar_url', '')
        }
    }), 200

@app.route('/api/profile/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Upload and validate user avatar"""
    file = request.files.get('avatar')
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    if file.mimetype not in ['image/jpeg', 'image/png']:
        return jsonify({'error': 'Invalid file type'}), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_AVATAR_SIZE:
        return jsonify({'error': 'File too large'}), 400

    header = file.read(512)
    file.seek(0)
    kind = imghdr.what(None, header)
    if kind not in ['jpeg', 'png']:
        return jsonify({'error': 'Invalid image content'}), 400

    username = session.get('user_id', 'user')
    safe_name = secure_filename(file.filename or f'{username}.png')
    filename = f'{username}_{int(datetime.now().timestamp())}_{safe_name}'
    save_path = os.path.join(AVATAR_DIR, filename)
    file.save(save_path)

    avatar_url = f'/uploads/profiles/{filename}'
    if username in VALID_USERS:
        VALID_USERS[username]['avatar_url'] = avatar_url

    session['avatar_url'] = avatar_url
    return jsonify({'avatarUrl': avatar_url}), 200

# ==================== Frontend Routes ====================

@app.route('/')
def index():
    """Serve the main dashboard"""
    # Redirect to login if not authenticated
    if 'user_id' not in session:
        return send_from_directory('frontend', 'login.html')
    return send_from_directory('frontend', 'index_new.html')

@app.route('/login')
def login_page():
    """Serve the login page"""
    if 'user_id' in session:
        return redirect('/')
    return send_from_directory('frontend', 'login.html')

@app.route('/uploads/<path:path>')
def serve_uploads(path):
    """Serve uploaded profile images"""
    return send_from_directory(os.path.join(app.static_folder, 'uploads'), path)

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    # Don't protect static files
    if os.path.exists(os.path.join('frontend', path)):
        return send_from_directory('frontend', path)
    
    # If not authenticated and requesting a page, redirect to login
    if 'user_id' not in session and not path.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg')):
        return send_from_directory('frontend', 'login.html')
    
    return send_from_directory('frontend', 'index.html')

# ==================== API Routes ====================

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    """Get dashboard data"""
    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        
        # Get employee count
        cursor.execute('SELECT COUNT(*) FROM employees')
        total_employees = cursor.fetchone()[0]
        
        # Get present employees today
        today = datetime.now().date()
        cursor.execute('''
            SELECT COUNT(DISTINCT employee_id) FROM attendance 
            WHERE date = ? AND status = 'Present'
        ''', (today,))
        present_today = cursor.fetchone()[0]
        
        conn.close()
        
        # Calculate PPE compliance (mock data)
        ppe_compliance = 94
        active_workers = present_today
        hazard_alerts = 2
        
        return jsonify({
            'ppe_compliance': ppe_compliance,
            'active_workers': active_workers,
            'hazard_alerts': hazard_alerts,
            'total_employees': total_employees
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    """Get recent incidents"""
    incidents = [
        {
            'id': '1',
            'time': '14:45',
            'type': 'No PPE Detected',
            'location': 'Zone B - Storage',
            'status': 'Pending'
        },
        {
            'id': '2',
            'time': '14:15',
            'type': 'Fire Alert',
            'location': 'Zone A - Processing',
            'status': 'Critical'
        }
    ]
    return jsonify({'incidents': incidents})

@app.route('/api/ppe-compliance', methods=['GET'])
def get_ppe_compliance():
    """Get PPE compliance data"""
    zone = request.args.get('zone', '')
    
    non_compliant = [
        {
            'employee_id': 'EMP001',
            'name': 'Tej Pratap',
            'missing_ppe': 'Helmet',
            'alerts': 3
        }
        
    ]
    
    return jsonify({
        'compliance_summary': {
            'helmets': 96,
            'safety_vests': 94
        },
        'non_compliant': non_compliant
    })

@app.route('/api/violations', methods=['GET'])
@login_required
@roles_required('admin', 'ops', 'staff')
def list_violations():
    """List violation snapshots with filters."""
    zone = request.args.get('zone', '').strip()
    camera = request.args.get('camera', '').strip()
    date_filter = request.args.get('date', '').strip()
    status = request.args.get('status', '').strip()
    limit = max(1, min(_parse_int(request.args.get('limit'), VIOLATION_LIST_LIMIT), 200))
    offset = max(0, _parse_int(request.args.get('offset'), 0))

    items = []
    matched = 0
    for path in _iter_violation_metadata():
        meta = _load_violation_metadata(path)
        if not meta:
            continue

        camera_id = meta.get('camera_id', path.parent.name)
        meta_zone = meta.get('zone', '')
        meta_status = meta.get('status', 'new')
        meta_date = ''
        ts_value = meta.get('timestamp') or meta.get('local_timestamp')
        if isinstance(ts_value, str) and len(ts_value) >= 10:
            meta_date = ts_value[:10]

        if zone and meta_zone != zone:
            continue
        if camera and camera_id != camera:
            continue
        if status and meta_status != status:
            continue
        if date_filter and meta_date != date_filter:
            continue

        if matched < offset:
            matched += 1
            continue

        base_name = path.stem
        violation_id = meta.get('id') or f"{camera_id}__{base_name}"
        items.append({
            'id': violation_id,
            'thumbnail_url': _violation_file_url(camera_id, meta.get('thumbnail') or meta.get('filename')),
            'timestamp': meta.get('timestamp'),
            'camera': camera_id,
            'zone': meta_zone,
            'status': meta_status,
            'missing_ppe': meta.get('missing_ppe', 'Helmet')
        })
        matched += 1
        if len(items) >= limit:
            break

    VIOLATION_API_LOGGER.info(
        "[violation_list] user=%s camera=%s zone=%s status=%s limit=%s",
        session.get('user_id', 'unknown'),
        camera or 'all',
        zone or 'all',
        status or 'all',
        limit,
    )

    return jsonify({
        'items': items,
        'limit': limit,
        'offset': offset,
        'count': len(items)
    })

@app.route('/api/violations/summary', methods=['GET'])
@login_required
@roles_required('admin', 'ops', 'staff')
def violation_summary():
    """Return counts by zone and status."""
    summary = {
        'total': 0,
        'by_zone': {},
        'by_status': {}
    }
    for path in _iter_violation_metadata():
        meta = _load_violation_metadata(path)
        if not meta:
            continue
        summary['total'] += 1
        zone = meta.get('zone', '') or 'Unassigned'
        status = meta.get('status', 'new') or 'new'
        summary['by_zone'][zone] = summary['by_zone'].get(zone, 0) + 1
        summary['by_status'][status] = summary['by_status'].get(status, 0) + 1
    return jsonify(summary)

@app.route('/api/violations/<violation_id>', methods=['GET'])
@login_required
@roles_required('admin', 'ops', 'staff')
def get_violation(violation_id):
    """Return violation metadata and image URLs."""
    meta_path = None
    camera_id = None
    base_name = None

    if '__' in violation_id:
        camera_id, base_name = violation_id.split('__', 1)
        camera_id = secure_filename(camera_id)
        base_name = secure_filename(base_name)
        if not camera_id or not base_name:
            return jsonify({'error': 'Invalid violation id'}), 400
        candidate = _violation_base_path() / camera_id / f"{base_name}.json"
        if candidate.exists():
            meta_path = candidate
        else:
            legacy_candidate = _violation_base_path() / f"{base_name}.json"
            if legacy_candidate.exists():
                meta_path = legacy_candidate

    if meta_path is None:
        for path in _iter_violation_metadata():
            if path.stem == violation_id:
                meta_path = path
                camera_id = path.parent.name
                base_name = path.stem
                break

    if meta_path is None or not meta_path.exists():
        return jsonify({'error': 'Violation not found'}), 404

    meta = _load_violation_metadata(meta_path)
    if not meta:
        return jsonify({'error': 'Violation metadata not found'}), 404

    camera_id = meta.get('camera_id', camera_id or meta_path.parent.name)
    base_name = meta_path.stem
    meta['id'] = meta.get('id') or f"{camera_id}__{base_name}"
    meta['image_url'] = _violation_file_url(camera_id, meta.get('filename'))
    meta['thumbnail_url'] = _violation_file_url(camera_id, meta.get('thumbnail') or meta.get('filename'))

    VIOLATION_API_LOGGER.info(
        "[violation_view] user=%s id=%s camera=%s",
        session.get('user_id', 'unknown'),
        meta['id'],
        camera_id,
    )

    return jsonify(meta)

@app.route('/api/violations/<violation_id>/review', methods=['POST'])
@login_required
@roles_required('admin', 'ops', 'staff')
def review_violation(violation_id):
    """Mark a violation as reviewed."""
    meta_path = None
    if '__' in violation_id:
        camera_id, base_name = violation_id.split('__', 1)
        camera_id = secure_filename(camera_id)
        base_name = secure_filename(base_name)
        if camera_id and base_name:
            candidate = _violation_base_path() / camera_id / f"{base_name}.json"
            if candidate.exists():
                meta_path = candidate
            else:
                legacy_candidate = _violation_base_path() / f"{base_name}.json"
                if legacy_candidate.exists():
                    meta_path = legacy_candidate

    if meta_path is None:
        for path in _iter_violation_metadata():
            if path.stem == violation_id:
                meta_path = path
                break

    if meta_path is None or not meta_path.exists():
        return jsonify({'error': 'Violation not found'}), 404

    meta = _load_violation_metadata(meta_path) or {}
    meta['status'] = 'reviewed'
    meta['reviewed_at'] = datetime.now().isoformat(timespec='seconds')
    meta['reviewed_by'] = session.get('user_id', 'unknown')

    tmp_path = meta_path.with_suffix(meta_path.suffix + '.tmp')
    with open(tmp_path, 'w', encoding='utf-8') as handle:
        json.dump(meta, handle, indent=2)
    os.replace(tmp_path, meta_path)

    VIOLATION_API_LOGGER.info(
        "[violation_review] user=%s id=%s",
        session.get('user_id', 'unknown'),
        meta.get('id') or _violation_id_from_path(meta_path),
    )

    return jsonify({'success': True, 'status': meta['status']})

@app.route('/api/violations/file/<camera_id>/<filename>', methods=['GET'])
@login_required
@roles_required('admin', 'ops', 'staff')
def get_violation_file(camera_id, filename):
    """Serve violation images from storage."""
    target = _safe_violation_path(camera_id, filename)
    if target is None or not target.exists():
        legacy_target = _legacy_violation_path(filename)
        if legacy_target is None or not legacy_target.exists():
            return jsonify({'error': 'File not found'}), 404
        target = legacy_target
    return send_file(target)

@app.route('/api/attendance', methods=['GET'])
def get_attendance_data():
    """Get attendance data for a specific date"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    department = request.args.get('department', '')
    
    try:
        report = get_attendance_report(date, date)
        
        present_count = 0
        absent_count = 0
        records = []
        
        if report:
            for emp_name, emp_id, rep_date, check_in, check_out, status in report:
                if status == 'Present':
                    present_count += 1
                else:
                    absent_count += 1
                
                # Handle both datetime and string formats
                check_in_str = '-'
                check_out_str = '-'
                
                if check_in:
                    if isinstance(check_in, str):
                        check_in_str = check_in.split(' ')[1][:5] if ' ' in check_in else check_in[:5]
                    else:
                        check_in_str = check_in.strftime('%H:%M')
                
                if check_out:
                    if isinstance(check_out, str):
                        check_out_str = check_out.split(' ')[1][:5] if ' ' in check_out else check_out[:5]
                    else:
                        check_out_str = check_out.strftime('%H:%M')
                
                records.append({
                    'employee_id': emp_id,
                    'name': emp_name,
                    'check_in': check_in_str,
                    'check_out': check_out_str,
                    'status': status
                })
        
        return jsonify({
            'present': present_count,
            'absent': absent_count,
            'records': records
        })
    except Exception as e:
        print(f"[ERROR] Attendance error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts', methods=['GET'])
def get_alerts_data():
    """Get all alerts and incidents"""
    alerts = [
        {
            'time': '14:15',
            'type': 'Fire Detection',
            'location': 'Zone C',
            'severity': 'Critical',
            'response_time': '2 min',
            'status': 'Resolved'
        },
        {
            'time': '14:45',
            'type': 'PPE Violation',
            'location': 'Zone B',
            'severity': 'Medium',
            'response_time': '3 min',
            'status': 'Pending'
        }
    ]
    
    return jsonify({'alerts': alerts})

@app.route('/api/analytics', methods=['GET'])
def get_analytics_data():
    """Get analytics and monthly reports"""
    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        
        # Get this month's attendance
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        cursor.execute('''
            SELECT COUNT(*) FROM attendance 
            WHERE date BETWEEN ? AND ? AND status = 'Present'
        ''', (month_start, today))
        monthly_present = cursor.fetchone()[0]
        
        conn.close()
        
        stats = {
            'total_incidents': 12,
            'resolved': 11,
            'avg_response_time': '4.5 min',
            'safety_score': 94,
            'monthly_present': monthly_present,
            'ppe_compliance_trend': [90, 91, 92, 93, 94, 94, 94],
            'incident_trend': [3, 2, 1, 2, 1, 0, 2]
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/employees', methods=['GET'])
def get_employees_list():
    """Get list of all employees"""
    try:
        employees = get_all_employees()
        emp_list = [
            {
                'id': emp[0],
                'name': emp[1],
                'employee_id': emp[2]
            }
            for emp in employees
        ]
        return jsonify({'employees': emp_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/employee/<int:emp_id>', methods=['GET'])
def get_employee_details(emp_id):
    """Get specific employee details"""
    try:
        emp = get_employee_by_id(emp_id)
        if emp:
            return jsonify({
                'id': emp[0],
                'name': emp[1],
                'employee_id': emp[2]
            })
        return jsonify({'error': 'Employee not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/zones', methods=['GET'])
def get_zones():
    """Get refinery zones"""
    zones = [
        {
            'id': 'A',
            'name': 'Processing Unit',
            'status': 'Operational',
            'workers': 45,
            'hazard_level': 'High'
        },
        {
            'id': 'B',
            'name': 'Storage Area',
            'status': 'Operational',
            'workers': 30,
            'hazard_level': 'Medium'
        },
        {
            'id': 'C',
            'name': 'Furnace Room',
            'status': 'Operational',
            'workers': 20,
            'hazard_level': 'Critical'
        },
        {
            'id': 'D',
            'name': 'Control Room',
            'status': 'Operational',
            'workers': 15,
            'hazard_level': 'Low'
        }
    ]
    return jsonify({'zones': zones})

def build_camera_response(camera_row):
    """Format camera DB rows for API response."""
    (
        camera_id, name, camera_type, stream_url, snapshot_url,
        _encrypted_credentials, status, location, created_at, created_by
    ) = camera_row

    return {
        'id': camera_id,
        'name': name,
        'type': camera_type,
        'status': status,
        'location': location,
        'created_at': created_at,
        'created_by': created_by,
        'thumbnail_url': f'/api/cameras/{camera_id}/thumbnail' if snapshot_url else None
    }

def fetch_snapshot_preview(snapshot_url, username=None, password=None):
    """Fetch snapshot bytes from an HTTP/HTTPS endpoint."""
    is_valid, error = validate_safe_url(snapshot_url, {'http', 'https'})
    if not is_valid:
        return None, error

    auth = (username, password) if username or password else None
    try:
        response = requests.get(snapshot_url, timeout=5, stream=True, auth=auth)
    except requests.RequestException:
        return None, 'Snapshot request failed'

    if response.status_code != 200:
        return None, f'Snapshot request failed with status {response.status_code}'

    content_type = response.headers.get('Content-Type', '')
    if not content_type.startswith('image/'):
        return None, 'Snapshot URL did not return an image'

    data = response.raw.read(CAMERA_PREVIEW_MAX_BYTES + 1)
    if len(data) > CAMERA_PREVIEW_MAX_BYTES:
        return None, 'Snapshot image is too large'

    return data, None

def fetch_stream_preview(stream_url, username=None, password=None):
    """Capture a frame from RTSP/HTTP stream using OpenCV."""
    is_valid, error = validate_safe_url(stream_url, {'rtsp', 'http', 'https'})
    if not is_valid:
        return None, error

    camera_url = apply_credentials_to_url(stream_url, username, password)
    try:
        cap = cv2.VideoCapture(camera_url)
        if not cap.isOpened():
            cap.release()
            return None, 'Unable to open stream'

        success, frame = cap.read()
        cap.release()
        if not success or frame is None:
            return None, 'Unable to read stream frame'

        success, buffer = cv2.imencode('.jpg', frame)
        if not success:
            return None, 'Unable to encode stream frame'

        return buffer.tobytes(), None
    except Exception:
        return None, 'Stream preview failed'

def placeholder_thumbnail_response():
    """Return a lightweight SVG placeholder for missing camera thumbnails."""
    svg = """<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180' viewBox='0 0 320 180'>
    <rect width='320' height='180' fill='#0b1851'/>
    <circle cx='160' cy='90' r='32' fill='#f59d10'/>
    <rect x='90' y='60' width='140' height='60' rx='10' fill='rgba(255,255,255,0.12)'/>
    <text x='160' y='140' font-size='14' font-family='Arial' fill='#ffffff' text-anchor='middle'>No Preview</text>
    </svg>"""
    return Response(svg, mimetype='image/svg+xml')

@app.route('/api/cameras/test', methods=['POST'])
@login_required
@admin_required
def test_camera_connection():
    """Validate camera connection and return a preview when possible."""
    data = request.get_json() or {}
    camera_type = (data.get('type') or '').strip().lower()
    stream_url = (data.get('stream_url') or '').strip()
    snapshot_url = (data.get('snapshot_url') or '').strip()
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if camera_type not in {'local', 'external'}:
        return jsonify({'success': False, 'message': 'Invalid camera type'}), 400

    if camera_type == 'local':
        return jsonify({
            'success': True,
            'message': 'Local camera preview is available in the browser.'
        }), 200

    if not stream_url:
        return jsonify({'success': False, 'message': 'Stream URL is required for external cameras'}), 400

    if snapshot_url:
        preview_bytes, error = fetch_snapshot_preview(snapshot_url, username, password)
    else:
        preview_bytes, error = fetch_stream_preview(stream_url, username, password)

    if error:
        return jsonify({'success': False, 'message': error}), 400

    preview_data_url = f"data:image/jpeg;base64,{base64.b64encode(preview_bytes).decode('utf-8')}"
    return jsonify({
        'success': True,
        'message': 'Camera connection successful',
        'preview': preview_data_url
    }), 200

@app.route('/api/cameras', methods=['POST'])
@login_required
@admin_required
def create_camera():
    """Create a new camera configuration."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    camera_type = (data.get('type') or '').strip().lower()
    stream_url = (data.get('stream_url') or '').strip()
    snapshot_url = (data.get('snapshot_url') or '').strip()
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    location = (data.get('location') or '').strip()

    if not name:
        return jsonify({'success': False, 'message': 'Camera name is required'}), 400

    if camera_type not in {'local', 'external'}:
        return jsonify({'success': False, 'message': 'Invalid camera type'}), 400

    if camera_type == 'external' and not stream_url:
        return jsonify({'success': False, 'message': 'Stream URL is required for external cameras'}), 400

    if stream_url:
        is_valid, error = validate_safe_url(stream_url, {'rtsp', 'http', 'https'})
        if not is_valid:
            return jsonify({'success': False, 'message': error}), 400

    if snapshot_url:
        is_valid, error = validate_safe_url(snapshot_url, {'http', 'https'})
        if not is_valid:
            return jsonify({'success': False, 'message': error}), 400

    encrypted_credentials = encrypt_camera_credentials(username, password)

    status = 'Online' if camera_type == 'local' else 'Offline'
    if camera_type == 'external':
        if snapshot_url:
            preview_bytes, error = fetch_snapshot_preview(snapshot_url, username, password)
        else:
            preview_bytes, error = fetch_stream_preview(stream_url, username, password)
        if error:
            status = 'Offline'
        else:
            status = 'Online'

    camera_id = add_camera(
        name=name,
        camera_type=camera_type,
        stream_url=stream_url,
        snapshot_url=snapshot_url,
        encrypted_credentials=encrypted_credentials,
        status=status,
        created_by=session.get('user_id'),
        location=location or None
    )

    log_camera_action('ADD', camera_id, name)

    return jsonify({
        'success': True,
        'message': 'Camera saved successfully',
        'camera_id': camera_id,
        'status': status
    }), 201

@app.route('/api/cameras', methods=['GET'])
@login_required
def list_cameras():
    """Return the list of configured cameras."""
    cameras = [build_camera_response(row) for row in get_cameras()]
    return jsonify({'cameras': cameras}), 200

@app.route('/api/cameras/<int:camera_id>/thumbnail', methods=['GET'])
@login_required
def camera_thumbnail(camera_id):
    """Return a thumbnail preview for a camera."""
    camera_row = get_camera_by_id(camera_id)
    if not camera_row:
        return jsonify({'error': 'Camera not found'}), 404

    (
        _camera_id, _name, camera_type, _stream_url, snapshot_url,
        encrypted_credentials, _status, _location, _created_at, _created_by
    ) = camera_row

    if camera_type == 'local' or not snapshot_url:
        return placeholder_thumbnail_response()

    credentials = decrypt_camera_credentials(encrypted_credentials)
    preview_bytes, error = fetch_snapshot_preview(snapshot_url, credentials.get('username'), credentials.get('password'))
    if error:
        return placeholder_thumbnail_response()

    return send_file(io.BytesIO(preview_bytes), mimetype='image/jpeg')

@app.route('/api/cameras/<int:camera_id>', methods=['DELETE'])
@login_required
@admin_required
def remove_camera(camera_id):
    """Delete a camera configuration."""
    camera_row = get_camera_by_id(camera_id)
    if not camera_row:
        return jsonify({'success': False, 'message': 'Camera not found'}), 404

    delete_camera(camera_id)
    log_camera_action('DELETE', camera_id, camera_row[1])
    return jsonify({'success': True, 'message': 'Camera deleted successfully'}), 200

@app.route('/api/camera-feeds', methods=['GET'])
def get_camera_feeds():
    """Get camera feed status"""
    cameras = [
        {
            'id': 'CAM-A1',
            'zone': 'A',
            'name': 'Zone A - Entrance',
            'status': 'Online',
            'last_frame': '2024-01-08 14:50:00'
        },
        {
            'id': 'CAM-B1',
            'zone': 'B',
            'name': 'Zone B - Storage',
            'status': 'Online',
            'last_frame': '2024-01-08 14:50:01'
        },
        {
            'id': 'CAM-C1',
            'zone': 'C',
            'name': 'Zone C - Furnace',
            'status': 'Online',
            'last_frame': '2024-01-08 14:50:02'
        }
    ]
    return jsonify({'cameras': cameras})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# ==================== CAMERA STREAMING WITH DETECTION ====================

# Global video capture object and lock for thread safety
camera_lock = Lock()
detection_model = None
camera = None
camera_running = False
camera_index = None
last_frame_at = None
camera_enabled = False
stream_thread = None
capture_thread = None
infer_thread = None
stream_stop = Event()
latest_frame_bytes = None
latest_frame_lock = Lock()
latest_frame_at = None
raw_frame = None
raw_frame_at = None
raw_frame_lock = Lock()
raw_frame_full = None
raw_frame_full_at = None
last_yolo_boxes = []
last_fire_detected = False
last_fire_areas = []
det_lock = Lock()

# Camera configuration (optional)
CAMERA_SOURCE = os.environ.get('CAMERA_SOURCE', '').strip()
# ==================== Violation Recorder Config ====================
def _load_app_config() -> dict:
    config_path = Path(__file__).resolve().parent / "config.json"
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes")


def _parse_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _env_first(names):
    for name in names:
        if name in os.environ:
            value = os.environ.get(name)
            if value is not None and value != "":
                return value
    return None


_app_config = _load_app_config()
_violation_cfg = _app_config.get("violation_capture", {}) if isinstance(_app_config, dict) else {}
_camera_cfg = _app_config.get("cameras", []) if isinstance(_app_config, dict) else []
_stream_cfg = _app_config.get("streaming", {}) if isinstance(_app_config, dict) else {}
_camera_zone_map = {
    cam.get("id"): cam.get("zone", "")
    for cam in _camera_cfg
    if isinstance(cam, dict) and cam.get("id")
}

VIOLATION_RECORDING_ENABLED = _parse_bool(
    _env_first(["VIOLATION_ENABLED", "ENABLE_VIOLATION_RECORDING"]),
    _violation_cfg.get("enabled", True),
)
VIOLATION_DEBOUNCE_FRAMES = _parse_int(
    _env_first(["VIOLATION_DEBOUNCE_FRAMES"]),
    _violation_cfg.get("debounce_frames", 2),
)
VIOLATION_CONFIDENCE_THRESHOLD = _parse_float(
    _env_first(["VIOLATION_CONFIDENCE_THRESHOLD"]),
    _violation_cfg.get("confidence_threshold", 0.45),
)
VIOLATION_MODEL_CONF = _parse_float(
    _env_first(["VIOLATION_MODEL_CONF", "MODEL_CONF"]),
    _violation_cfg.get("model_confidence", 0.25),
)
VIOLATION_MODEL_IOU = _parse_float(
    _env_first(["VIOLATION_MODEL_IOU", "MODEL_IOU"]),
    _violation_cfg.get("model_iou", 0.45),
)
VIOLATION_MODEL_IMGSZ = _parse_int(
    _env_first(["VIOLATION_MODEL_IMGSZ", "MODEL_IMGSZ"]),
    _violation_cfg.get("model_imgsz", 640),
)
VIOLATION_MIN_OVERLAP_IOU = _parse_float(
    _env_first(["VIOLATION_MIN_OVERLAP_IOU", "MIN_OVERLAP_IOU"]),
    _violation_cfg.get("min_overlap_iou", 0.1),
)
VIOLATION_PERSON_THRESHOLD = _parse_float(
    _env_first(["VIOLATION_PERSON_THRESHOLD", "PERSON_THRESHOLD", "THRESH_P"]),
    _violation_cfg.get("person_confidence_threshold", VIOLATION_CONFIDENCE_THRESHOLD),
)
VIOLATION_NO_HELMET_THRESHOLD = _parse_float(
    _env_first(["VIOLATION_NO_HELMET_THRESHOLD", "NO_HELMET_THRESHOLD", "THRESH_H"]),
    _violation_cfg.get("no_helmet_confidence_threshold", VIOLATION_CONFIDENCE_THRESHOLD),
)
VIOLATION_HELMET_THRESHOLD = _parse_float(
    _env_first(["VIOLATION_HELMET_THRESHOLD", "HELMET_THRESHOLD"]),
    _violation_cfg.get("helmet_confidence_threshold", VIOLATION_CONFIDENCE_THRESHOLD),
)
VIOLATION_HEAD_RATIO = _parse_float(
    _env_first(["VIOLATION_HEAD_RATIO", "HEAD_RATIO"]),
    _violation_cfg.get("head_ratio", 0.3),
)
VEST_CONF_STRICT = _parse_float(
    _env_first(["VEST_CONF_STRICT"]),
    _violation_cfg.get("vest_conf_strict", 0.45),
)
VEST_CONF_SOFT = _parse_float(
    _env_first(["VEST_CONF_SOFT"]),
    _violation_cfg.get("vest_conf_soft", 0.3),
)
VEST_COLOR_COVERAGE_MIN = _parse_float(
    _env_first(["VEST_COLOR_COVERAGE_MIN", "VEST_COLOR_MIN"]),
    _violation_cfg.get("vest_color_coverage_min", 0.12),
)
VEST_TORSO_TOP_RATIO = _parse_float(
    _env_first(["VEST_TORSO_TOP_RATIO"]),
    _violation_cfg.get("vest_torso_top_ratio", 0.25),
)
VEST_TORSO_BOTTOM_RATIO = _parse_float(
    _env_first(["VEST_TORSO_BOTTOM_RATIO"]),
    _violation_cfg.get("vest_torso_bottom_ratio", 0.85),
)
VEST_MIN_BOX_AREA = _parse_int(
    _env_first(["VEST_MIN_BOX_AREA"]),
    _violation_cfg.get("vest_min_box_area", 300),
)
VIOLATION_NO_VEST_THRESHOLD = _parse_float(
    _env_first(["VIOLATION_NO_VEST_THRESHOLD", "NO_VEST_THRESHOLD"]),
    _violation_cfg.get("no_vest_confidence_threshold", VIOLATION_CONFIDENCE_THRESHOLD),
)
VIOLATION_VEST_THRESHOLD = _parse_float(
    _env_first(["VIOLATION_VEST_THRESHOLD", "VEST_THRESHOLD"]),
    _violation_cfg.get("vest_confidence_threshold", VIOLATION_CONFIDENCE_THRESHOLD),
)
COLOR_CALIBRATION_PATH = (
    _env_first(["COLOR_CALIBRATION_PATH"]) or _violation_cfg.get("color_calibration_path")
)
COLOR_THRESHOLDS_CFG = _violation_cfg.get("color_thresholds", {}) if isinstance(_violation_cfg, dict) else {}
COLOR_THRESHOLDS = thresholds_from_cfg(COLOR_THRESHOLDS_CFG)
COLOR_CALIBRATION = load_calibration(COLOR_CALIBRATION_PATH) if COLOR_CALIBRATION_PATH else {}
CALIBRATED_THRESHOLDS = thresholds_from_cfg(COLOR_CALIBRATION.get("thresholds", {})) if COLOR_CALIBRATION else COLOR_THRESHOLDS
THRESH_H = VIOLATION_NO_HELMET_THRESHOLD
THRESH_P = VIOLATION_PERSON_THRESHOLD
STREAM_FPS = _parse_float(
    _env_first(["STREAM_FPS"]),
    _stream_cfg.get("fps", 20.0),
)
STREAM_JPEG_QUALITY = _parse_int(
    _env_first(["STREAM_JPEG_QUALITY"]),
    _stream_cfg.get("jpeg_quality", 75),
)
STREAM_PLACEHOLDER_QUALITY = _parse_int(
    _env_first(["STREAM_PLACEHOLDER_QUALITY"]),
    _stream_cfg.get("placeholder_quality", 85),
)
STREAM_MIN_SEND_INTERVAL = _parse_float(
    _env_first(["STREAM_MIN_SEND_INTERVAL"]),
    _stream_cfg.get("min_send_interval", 0.02),
)
VIOLATION_QUEUE_MAX = _parse_int(
    _env_first(["VIOLATION_QUEUE_MAX"]),
    _violation_cfg.get("queue_max", 200),
)
VIOLATION_RATE_LIMIT = _parse_int(
    _env_first(["VIOLATION_RATE_LIMIT_PER_MIN"]),
    _violation_cfg.get("rate_limit_per_min", 30),
)
VIOLATION_RATE_LIMIT_SECONDS = _parse_float(
    _env_first(["RATE_LIMIT_SECONDS", "VIOLATION_RATE_LIMIT_SECONDS"]),
    _violation_cfg.get("rate_limit_seconds", 10.0),
)
VIOLATION_THUMBNAIL_WIDTH = _parse_int(
    _env_first(["VIOLATION_THUMBNAIL_WIDTH", "THUMBNAIL_WIDTH"]),
    _violation_cfg.get("thumbnail_width", 200),
)
VIOLATION_LIST_LIMIT = _parse_int(
    _env_first(["VIOLATION_LIST_LIMIT"]),
    _violation_cfg.get("list_limit", 6),
)
VIOLATION_UPLOAD_ENABLED = _parse_bool(
    _env_first(["UPLOAD_ENABLED", "VIOLATION_UPLOAD_ENABLED"]),
    _violation_cfg.get("upload_enabled", False),
)
VIOLATION_UPLOAD_ENDPOINT = (
    _env_first(["VIOLATION_UPLOAD_ENDPOINT", "UPLOAD_ENDPOINT"]) or _violation_cfg.get("upload_endpoint")
)
VIOLATIONS_BASE_PATH = (
    _env_first(["VIOLATION_SAVE_PATH", "VIOLATIONS_BASE_PATH"]) or _violation_cfg.get("save_path") or "violations"
)
VIOLATION_SAVE_CROP = _parse_bool(
    _env_first(["VIOLATION_SAVE_CROP"]),
    _violation_cfg.get("save_crop", True),
)
VIOLATION_OBFUSCATE = _parse_bool(
    _env_first(["VIOLATION_OBFUSCATE"]),
    _violation_cfg.get("obfuscate_faces", False),
)
VIOLATION_MODEL_NAME = _env_first(["VIOLATION_MODEL_NAME"]) or _violation_cfg.get("model", "ppe.pt")
CAMERA_ID = _env_first(["VIOLATION_CAMERA_ID", "CAMERA_ID"]) or _violation_cfg.get("camera_id", "CAM-DEFAULT")
VIOLATION_RETENTION_DAYS = _parse_int(
    _env_first(["VIOLATION_RETENTION_DAYS"]),
    _violation_cfg.get("retention_days", 30),
)
VIOLATION_OVERLAY_TIMESTAMP = _parse_bool(
    _env_first(["VIOLATION_OVERLAY_TIMESTAMP"]),
    _violation_cfg.get("overlay_timestamp", True),
)
VIOLATION_MAX_CONCURRENT_WRITES = _parse_int(
    _env_first(["VIOLATION_MAX_CONCURRENT_WRITES"]),
    _violation_cfg.get("max_concurrent_writes", 2),
)
VIOLATION_TRACK_GRID = _parse_int(
    _env_first(["VIOLATION_TRACK_GRID"]),
    _violation_cfg.get("track_grid", 60),
)
VIOLATION_TRACK_TIMEOUT_SEC = _parse_float(
    _env_first(["VIOLATION_TRACK_TIMEOUT_SEC"]),
    _violation_cfg.get("track_timeout_sec", 2.0),
)
VIOLATION_TRACK_COOLDOWN_SEC = _parse_float(
    _env_first(["VIOLATION_TRACK_COOLDOWN_SEC"]),
    _violation_cfg.get("track_cooldown_sec", VIOLATION_RATE_LIMIT_SECONDS),
)

violation_recorder = ViolationRecorder(
    base_path=VIOLATIONS_BASE_PATH,
    queue_maxsize=VIOLATION_QUEUE_MAX,
    enable=VIOLATION_RECORDING_ENABLED,
    rate_limit_per_minute=VIOLATION_RATE_LIMIT,
    rate_limit_seconds=VIOLATION_RATE_LIMIT_SECONDS,
    save_crops=VIOLATION_SAVE_CROP,
    obfuscate_faces=VIOLATION_OBFUSCATE,
    model_name=VIOLATION_MODEL_NAME,
    default_camera_id=CAMERA_ID,
    retention_days=VIOLATION_RETENTION_DAYS,
    overlay_timestamp=VIOLATION_OVERLAY_TIMESTAMP,
    max_concurrent_writes=VIOLATION_MAX_CONCURRENT_WRITES,
    thumbnail_width=VIOLATION_THUMBNAIL_WIDTH,
    upload_enabled=VIOLATION_UPLOAD_ENABLED,
    upload_endpoint=VIOLATION_UPLOAD_ENDPOINT,
)
CAMERA_INDEX = os.environ.get('CAMERA_INDEX', '').strip()

def _camera_zone(camera_id: str) -> str:
    return _camera_zone_map.get(camera_id, "")

def _violation_base_path() -> Path:
    return Path(VIOLATIONS_BASE_PATH).resolve()

def _safe_violation_path(camera_id: str, filename: str) -> Optional[Path]:
    safe_camera = secure_filename(camera_id)
    safe_filename = secure_filename(filename)
    if safe_camera != camera_id or safe_filename != filename:
        return None
    if not safe_filename.lower().endswith((".jpg", ".jpeg", ".png")):
        return None
    base_dir = _violation_base_path()
    target = (base_dir / safe_camera / safe_filename).resolve()
    if base_dir not in target.parents:
        return None
    return target

def _iter_violation_metadata():
    base_dir = _violation_base_path()
    if not base_dir.exists():
        return []
    try:
        return sorted(base_dir.rglob("violation_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return []

def _load_violation_metadata(path: Path) -> Optional[dict]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None

def _violation_id_from_path(path: Path) -> str:
    camera_id = path.parent.name
    base_name = path.stem
    return f"{camera_id}__{base_name}"

def _violation_file_url(camera_id: str, filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    return f"/api/violations/file/{camera_id}/{filename}"

def _legacy_violation_path(filename: str) -> Optional[Path]:
    safe_filename = secure_filename(filename)
    if safe_filename != filename:
        return None
    base_dir = _violation_base_path()
    target = (base_dir / safe_filename).resolve()
    if base_dir not in target.parents:
        return None
    return target

def init_detection_model():
    """Initialize YOLO detection model"""
    global detection_model
    try:
        from ultralytics import YOLO
        if detection_model is None:
            # Try to load PPE detection model
            if os.path.exists('YOLO-Weights/ppe.pt'):
                detection_model = YOLO('YOLO-Weights/ppe.pt')
                print("[INFO] PPE Detection Model Loaded Successfully")
                return True
            else:
                print("[WARNING] PPE model not found at YOLO-Weights/ppe.pt")
                return False
    except Exception as e:
        print(f"[WARNING] Could not load YOLO model: {e}")
        return False

def detect_fire(frame):
    """Detect fire using HSV color ranges"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Fire detection (red-orange colors)
    lower_fire1 = np.array([0, 100, 100])
    upper_fire1 = np.array([10, 255, 255])
    mask_fire1 = cv2.inRange(hsv, lower_fire1, upper_fire1)
    
    lower_fire2 = np.array([170, 100, 100])
    upper_fire2 = np.array([180, 255, 255])
    mask_fire2 = cv2.inRange(hsv, lower_fire2, upper_fire2)
    
    fire_mask = cv2.bitwise_or(mask_fire1, mask_fire2)
    
    # Find contours
    fire_contours, _ = cv2.findContours(fire_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    fire_areas = []
    
    # Filter contours by area
    for contour in fire_contours:
        area = cv2.contourArea(contour)
        if area > 500:
            fire_areas.append(contour)
    
    fire_detected = len(fire_areas) > 0
    
    return fire_detected, fire_areas

def init_camera():
    """Initialize camera capture.

    Tries multiple indices and Windows backends to handle common camera issues.
    Supports CAMERA_SOURCE or CAMERA_INDEX overrides.
    """
    global camera, camera_index
    with camera_lock:
        if camera is not None and camera.isOpened():
            return True

        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass
            camera = None
            camera_index = None

        backends = [None]
        if os.name == "nt":
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, None]

        def try_open(source, backend):
            test_cam = cv2.VideoCapture(source) if backend is None else cv2.VideoCapture(source, backend)
            if not test_cam.isOpened():
                test_cam.release()
                return None
            try:
                test_cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            # Warm up a frame to ensure it really works
            for _ in range(3):
                ret, _ = test_cam.read()
                if ret:
                    return test_cam
            test_cam.release()
            return None

        # If CAMERA_SOURCE is provided (e.g., rtsp/http/file), try it first
        if CAMERA_SOURCE:
            for backend in backends:
                cam = try_open(CAMERA_SOURCE, backend)
                if cam is not None:
                    camera = cam
                    camera_index = CAMERA_SOURCE
                    backend_name = "DEFAULT" if backend is None else str(backend)
                    print(f"[INFO] Camera opened from CAMERA_SOURCE (backend {backend_name})")
                    return True

        # If CAMERA_INDEX is provided, try that index only
        if CAMERA_INDEX.isdigit():
            idx = int(CAMERA_INDEX)
            for backend in backends:
                cam = try_open(idx, backend)
                if cam is not None:
                    camera = cam
                    camera_index = idx
                    backend_name = "DEFAULT" if backend is None else str(backend)
                    print(f"[INFO] Camera opened at index {idx} (backend {backend_name})")
                    return True

        # Otherwise, try common indices
        for idx in (0, 1, 2, 3):
            for backend in backends:
                cam = try_open(idx, backend)
                if cam is not None:
                    camera = cam
                    camera_index = idx
                    backend_name = "DEFAULT" if backend is None else str(backend)
                    print(f"[INFO] Camera opened at index {idx} (backend {backend_name})")
                    return True

        print("[WARNING] Could not open any camera (indices 0-3). Streaming will show placeholder.")
        return False

def _update_latest_frame(frame, quality=80):
    global latest_frame_bytes, latest_frame_at
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ret:
        return
    with latest_frame_lock:
        latest_frame_bytes = buffer.tobytes()
        latest_frame_at = datetime.now().isoformat()


def _camera_capture_worker(frame_size):
    """Capture thread that keeps the latest frame fresh."""
    global camera, camera_running, raw_frame, raw_frame_at, last_frame_at, raw_frame_full, raw_frame_full_at
    camera_running = True
    while not stream_stop.is_set():
        if not camera_enabled or not init_camera():
            last_frame_at = None
            time.sleep(0.05)
            continue

        success, frame = camera.read()
        if not success:
            time.sleep(0.02)
            continue

        last_frame_at = datetime.now().isoformat()
        full_frame = frame
        frame = cv2.resize(frame, frame_size)
        with raw_frame_lock:
            raw_frame = frame
            raw_frame_full = full_frame
            raw_frame_at = time.monotonic()
            raw_frame_full_at = raw_frame_at

    camera_running = False


def _camera_infer_worker(frame_size, yolo_input_size):
    """Inference thread that updates detection overlays."""
    global detection_model, last_yolo_boxes, last_fire_detected, last_fire_areas

    init_detection_model()

    ppe_classes = [
        'Hardhat', None, 'NO-Hardhat', None,
        'NO-Safety Vest', 'Person',
        'Safety Cone', 'Safety Vest',
        'machinery', 'vehicle'
    ]

    def _iou(box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        if inter_area <= 0:
            return 0.0
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter_area
        return inter_area / union if union > 0 else 0.0

    def _best_person_for_box(box, person_list):
        best_iou = 0.0
        best_box = None
        for (px1, py1, px2, py2, _) in person_list:
            iou = _iou(box, (px1, py1, px2, py2))
            if iou > best_iou:
                best_iou = iou
                best_box = (px1, py1, px2, py2)
        return best_box

    def _torso_box(person_bbox, top_ratio=0.25, bottom_ratio=0.85):
        x1, y1, x2, y2 = person_bbox
        top = y1 + int((y2 - y1) * top_ratio)
        bottom = y1 + int((y2 - y1) * bottom_ratio)
        return (x1, top, x2, bottom)

    yolo_min_interval = 1.2
    fire_min_interval = 0.2
    last_yolo_infer_at = 0.0
    last_fire_infer_at = 0.0
    scale_x = frame_size[0] / yolo_input_size[0]
    scale_y = frame_size[1] / yolo_input_size[1]
    violation_consecutive = 0
    track_counts = {}
    track_last_seen = {}
    track_last_capture = {}
    frame_id = 0

    while not stream_stop.is_set():
        with raw_frame_lock:
            frame = raw_frame.copy() if raw_frame is not None else None
            full_frame = raw_frame_full.copy() if raw_frame_full is not None else None
        if frame is None:
            time.sleep(0.02)
            continue

        now = time.monotonic()

        if now - last_fire_infer_at >= fire_min_interval:
            last_fire_infer_at = now
            fire_detected, fire_areas = detect_fire(frame)
            with det_lock:
                last_fire_detected = fire_detected
                last_fire_areas = fire_areas

        if detection_model is not None and now - last_yolo_infer_at >= yolo_min_interval:
            last_yolo_infer_at = now
            boxes = []
            person_conf = 0.0
            helmet_conf = 0.0
            no_helmet_conf = 0.0
            best_person_bbox = None
            no_helmet_boxes = []
            hardhat_boxes = []
            vest_boxes = []
            no_vest_boxes = []
            person_boxes = []
            try:
                infer_frame = cv2.resize(frame, yolo_input_size)
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                mask = build_color_mask(hsv, CALIBRATED_THRESHOLDS)
                mask = refine_mask(mask, kernel_size=7)
                results = detection_model.predict(
                    infer_frame,
                    conf=VIOLATION_MODEL_CONF,
                    iou=VIOLATION_MODEL_IOU,
                    imgsz=VIOLATION_MODEL_IMGSZ,
                    verbose=False,
                )
                for r in results:
                    for box in r.boxes:
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        if cls >= len(ppe_classes):
                            continue
                        class_name = ppe_classes[cls]
                        if not class_name:
                            continue
                        x1, y1, x2, y2 = box.xyxy[0]
                        x1 = int(x1 * scale_x)
                        y1 = int(y1 * scale_y)
                        x2 = int(x2 * scale_x)
                        y2 = int(y2 * scale_y)
                        if class_name == "Safety Vest":
                            area = (x2 - x1) * (y2 - y1)
                            if area < VEST_MIN_BOX_AREA:
                                continue
                            person_match = _best_person_for_box((x1, y1, x2, y2), person_boxes)
                            torso = _torso_box(person_match, VEST_TORSO_TOP_RATIO, VEST_TORSO_BOTTOM_RATIO) if person_match else (x1, y1, x2, y2)
                            coverage = color_coverage(mask, torso)
                            if not (conf >= VEST_CONF_STRICT or (conf >= VEST_CONF_SOFT and coverage >= VEST_COLOR_COVERAGE_MIN)):
                                continue
                            vest_boxes.append((x1, y1, x2, y2, conf, coverage))

                        if class_name == "NO-Safety Vest":
                            no_vest_boxes.append((x1, y1, x2, y2, conf))

                        color = (0, 255, 0) if "NO" not in class_name else (0, 0, 255)
                        label = f"{class_name} {conf:.2f}"
                        boxes.append((x1, y1, x2, y2, color, label))

                        if class_name == "Person" and conf >= THRESH_P:
                            if conf > person_conf:
                                person_conf = conf
                                best_person_bbox = (x1, y1, x2, y2)
                            person_boxes.append((x1, y1, x2, y2, conf))
                        elif class_name == "Hardhat":
                            if conf > helmet_conf:
                                helmet_conf = conf
                            hardhat_boxes.append((x1, y1, x2, y2, conf))
                        elif class_name == "NO-Hardhat":
                            if conf > no_helmet_conf:
                                no_helmet_conf = conf
                            no_helmet_boxes.append((x1, y1, x2, y2, conf))
            except Exception:
                boxes = []

            with det_lock:
                last_yolo_boxes = boxes

            frame_id += 1
            violation_condition, matched_conf = is_helmet_violation(
                person_conf,
                best_person_bbox,
                no_helmet_boxes,
                hardhat_boxes,
                THRESH_P,
                THRESH_H,
                VIOLATION_HELMET_THRESHOLD,
                VIOLATION_MIN_OVERLAP_IOU,
                VIOLATION_HEAD_RATIO,
            )

            if violation_condition and best_person_bbox is not None:
                violation_consecutive += 1
            else:
                violation_consecutive = 0

            now_ts = time.monotonic()
            if VIOLATION_RECORDING_ENABLED and person_boxes:
                if VIOLATION_TRACK_GRID <= 0:
                    track_grid = 60
                else:
                    track_grid = VIOLATION_TRACK_GRID

                for (px1, py1, px2, py2, pconf) in person_boxes:
                    violated, overlap_conf = is_helmet_violation(
                        pconf,
                        (px1, py1, px2, py2),
                        no_helmet_boxes,
                        hardhat_boxes,
                        THRESH_P,
                        THRESH_H,
                        VIOLATION_HELMET_THRESHOLD,
                        VIOLATION_MIN_OVERLAP_IOU,
                        VIOLATION_HEAD_RATIO,
                    )
                    if not violated:
                        continue

                    cx = int((px1 + px2) / 2)
                    cy = int((py1 + py2) / 2)
                    track_key = ("helmet", int(cx // track_grid), int(cy // track_grid))

                    track_counts[track_key] = track_counts.get(track_key, 0) + 1
                    track_last_seen[track_key] = now_ts

                    last_capture = track_last_capture.get(track_key, 0.0)
                    if track_counts[track_key] < VIOLATION_DEBOUNCE_FRAMES:
                        continue
                    if VIOLATION_TRACK_COOLDOWN_SEC > 0 and (now_ts - last_capture) < VIOLATION_TRACK_COOLDOWN_SEC:
                        continue

                    track_counts[track_key] = 0
                    track_last_capture[track_key] = now_ts

                    detection_id = uuid.uuid4().hex
                    violation_frame = full_frame if full_frame is not None else frame
                    violation_bbox = (px1, py1, px2, py2)
                    if full_frame is not None:
                        full_h, full_w = full_frame.shape[:2]
                        scale_full_x = full_w / frame_size[0]
                        scale_full_y = full_h / frame_size[1]
                        violation_bbox = (
                            int(px1 * scale_full_x),
                            int(py1 * scale_full_y),
                            int(px2 * scale_full_x),
                            int(py2 * scale_full_y),
                        )

                    meta = {
                        "camera_id": CAMERA_ID,
                        "zone": _camera_zone(CAMERA_ID),
                        "missing_ppe": "Helmet",
                        "helmet_confidence": round(helmet_conf, 4),
                        "person_confidence": round(pconf, 4),
                        "frame_id": frame_id,
                        "frame_number": frame_id,
                        "detection_id": detection_id,
                        "model_name": VIOLATION_MODEL_NAME,
                        "confidence": round(overlap_conf, 4),
                    }
                    violation_recorder.enqueue_violation(violation_frame, violation_bbox, meta)

                if no_vest_boxes:
                    for (px1, py1, px2, py2, pconf) in person_boxes:
                        best_no_vest_conf = 0.0
                        best_vest_conf = 0.0
                        for (vx1, vy1, vx2, vy2, vconf) in no_vest_boxes:
                            iou = _iou((px1, py1, px2, py2), (vx1, vy1, vx2, vy2))
                            if iou >= VIOLATION_MIN_OVERLAP_IOU and vconf > best_no_vest_conf:
                                best_no_vest_conf = vconf
                        for (vx1, vy1, vx2, vy2, vconf, _) in vest_boxes:
                            iou = _iou((px1, py1, px2, py2), (vx1, vy1, vx2, vy2))
                            if iou >= VIOLATION_MIN_OVERLAP_IOU and vconf > best_vest_conf:
                                best_vest_conf = vconf
                        if pconf < THRESH_P or best_no_vest_conf < VIOLATION_NO_VEST_THRESHOLD:
                            continue
                        if best_vest_conf >= VIOLATION_VEST_THRESHOLD:
                            continue

                        cx = int((px1 + px2) / 2)
                        cy = int((py1 + py2) / 2)
                        track_key = ("vest", int(cx // track_grid), int(cy // track_grid))
                        track_counts[track_key] = track_counts.get(track_key, 0) + 1
                        track_last_seen[track_key] = now_ts
                        last_capture = track_last_capture.get(track_key, 0.0)
                        if track_counts[track_key] < VIOLATION_DEBOUNCE_FRAMES:
                            continue
                        if VIOLATION_TRACK_COOLDOWN_SEC > 0 and (now_ts - last_capture) < VIOLATION_TRACK_COOLDOWN_SEC:
                            continue

                        track_counts[track_key] = 0
                        track_last_capture[track_key] = now_ts
                        detection_id = uuid.uuid4().hex
                        violation_frame = full_frame if full_frame is not None else frame
                        violation_bbox = (px1, py1, px2, py2)
                        if full_frame is not None:
                            full_h, full_w = full_frame.shape[:2]
                            scale_full_x = full_w / frame_size[0]
                            scale_full_y = full_h / frame_size[1]
                            violation_bbox = (
                                int(px1 * scale_full_x),
                                int(py1 * scale_full_y),
                                int(px2 * scale_full_x),
                                int(py2 * scale_full_y),
                            )

                        meta = {
                            "camera_id": CAMERA_ID,
                            "zone": _camera_zone(CAMERA_ID),
                            "missing_ppe": "Safety Vest",
                            "vest_confidence": round(best_vest_conf, 4),
                            "no_vest_confidence": round(best_no_vest_conf, 4),
                            "person_confidence": round(pconf, 4),
                            "frame_id": frame_id,
                            "frame_number": frame_id,
                            "detection_id": detection_id,
                            "model_name": VIOLATION_MODEL_NAME,
                            "confidence": round(best_no_vest_conf, 4),
                        }
                        violation_recorder.enqueue_violation(violation_frame, violation_bbox, meta)

                stale_keys = [
                    key for key, last_seen in track_last_seen.items()
                    if now_ts - last_seen > VIOLATION_TRACK_TIMEOUT_SEC
                ]
                for key in stale_keys:
                    track_counts.pop(key, None)
                    track_last_seen.pop(key, None)
                    track_last_capture.pop(key, None)

            if VIOLATION_RECORDING_ENABLED and violation_consecutive >= VIOLATION_DEBOUNCE_FRAMES:
                violation_consecutive = 0
                detection_id = uuid.uuid4().hex
                violation_frame = full_frame if full_frame is not None else frame
                violation_bbox = best_person_bbox
                if full_frame is not None and best_person_bbox is not None:
                    full_h, full_w = full_frame.shape[:2]
                    scale_full_x = full_w / frame_size[0]
                    scale_full_y = full_h / frame_size[1]
                    violation_bbox = (
                        int(best_person_bbox[0] * scale_full_x),
                        int(best_person_bbox[1] * scale_full_y),
                        int(best_person_bbox[2] * scale_full_x),
                        int(best_person_bbox[3] * scale_full_y),
                    )
                meta = {
                    "camera_id": CAMERA_ID,
                    "zone": _camera_zone(CAMERA_ID),
                    "missing_ppe": "Helmet",
                    "helmet_confidence": round(helmet_conf, 4),
                    "person_confidence": round(person_conf, 4),
                    "frame_id": frame_id,
                    "frame_number": frame_id,
                    "detection_id": detection_id,
                    "model_name": VIOLATION_MODEL_NAME,
                    "confidence": round(matched_conf, 4),
                }
                violation_recorder.enqueue_violation(violation_frame, violation_bbox, meta)

        time.sleep(0.01)


def _camera_stream_worker():
    """Encoder thread that overlays detections and updates MJPEG buffer."""
    alarm_triggered = False
    frame_size = (640, 480)
    target_frame_interval = 1.0 / max(1.0, STREAM_FPS)
    placeholder_base = np.zeros((480, 640, 3), dtype=np.uint8)
    for i in range(480):
        placeholder_base[i, :] = [int(30 + i * 0.1), int(50 + i * 0.05), int(100 + i * 0.08)]

    while not stream_stop.is_set():
        loop_start = time.monotonic()

        if not camera_enabled or not init_camera():
            if is_alarm_active():
                stop_fire_alarm()
            frame = placeholder_base.copy()
            cv2.putText(frame, "Camera Not Available", (120, 220),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 165, 255), 2)
            cv2.putText(frame, "Deploy on machine with webcam", (100, 270),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 1)
            cv2.putText(frame, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
            _update_latest_frame(frame, quality=STREAM_PLACEHOLDER_QUALITY)
            time.sleep(0.033)
            continue

        with raw_frame_lock:
            frame = raw_frame.copy() if raw_frame is not None else None
        if frame is None:
            time.sleep(0.01)
            continue

        with det_lock:
            fire_detected = last_fire_detected
            fire_areas = list(last_fire_areas)
            yolo_boxes = list(last_yolo_boxes)

        if fire_detected:
            if not alarm_triggered:
                start_fire_alarm()
                alarm_triggered = True
            for contour in fire_areas:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 3)
            cv2.putText(frame, "FIRE DETECTED!", (50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        else:
            if alarm_triggered:
                stop_fire_alarm()
                alarm_triggered = False

        for x1, y1, x2, y2, color, label in yolo_boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 10),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.putText(frame, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        cv2.circle(frame, (620, 20), 8, (0, 0, 255), -1)
        cv2.putText(frame, "LIVE", (545, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

        _update_latest_frame(frame, quality=STREAM_JPEG_QUALITY)

        elapsed = time.monotonic() - loop_start
        if elapsed < target_frame_interval:
            time.sleep(target_frame_interval - elapsed)

    if alarm_triggered:
        stop_fire_alarm()


def _ensure_stream_worker():
    global stream_thread, capture_thread, infer_thread
    if stream_thread is None or not stream_thread.is_alive():
        stream_stop.clear()
        capture_thread = Thread(target=_camera_capture_worker, args=((640, 480),), daemon=True)
        infer_thread = Thread(target=_camera_infer_worker, args=((640, 480), (640, 480)), daemon=True)
        stream_thread = Thread(target=_camera_stream_worker, daemon=True)
        capture_thread.start()
        infer_thread.start()
        stream_thread.start()


def generate_frames():
    """Generate frames from the background stream worker."""
    _ensure_stream_worker()
    last_sent_at = None
    while not stream_stop.is_set():
        with latest_frame_lock:
            frame_bytes = latest_frame_bytes
            frame_at = latest_frame_at
        if frame_bytes and frame_at != last_sent_at:
            last_sent_at = frame_at
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(STREAM_MIN_SEND_INTERVAL)

@app.route('/video_feed')
def video_feed():
    """Video streaming endpoint - serves MJPEG stream"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/video/status')
def video_status():
    """Get video streaming status"""
    global camera, camera_running, camera_index, last_frame_at, camera_enabled
    return jsonify({
        'streaming': camera is not None and camera.isOpened(),
        'camera_running': camera_running,
        'camera_index': camera_index,
        'last_frame_at': last_frame_at,
        'camera_enabled': camera_enabled,
        'url': '/video_feed',
        'format': 'MJPEG'
    })

@app.route('/api/camera/control', methods=['POST'])
@login_required
def camera_control():
    """Enable or disable the camera at the backend level."""
    global camera_enabled, camera
    try:
        data = request.get_json() or {}
        enable = bool(data.get('enable', False))
        camera_enabled = enable

        if not enable:
            stream_stop.set()
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass
                camera = None
            stop_fire_alarm()
        else:
            _ensure_stream_worker()
        return jsonify({'success': True, 'enabled': camera_enabled})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audit/camera', methods=['POST'])
@login_required
def audit_camera():
    """Log camera enable/disable actions for compliance."""
    try:
        data = request.get_json() or {}
        action = data.get('action', 'unknown')
        status = data.get('status', 'unknown')
        user = data.get('user', 'unknown')
        ip = request.remote_addr

        os.makedirs('logs', exist_ok=True)
        log_line = f"{datetime.now().isoformat()} | user={user} | action={action} | status={status} | ip={ip}\n"
        with open(os.path.join('logs', 'camera_audit.log'), 'a', encoding='utf-8') as f:
            f.write(log_line)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not Found', 'message': 'The requested resource was not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server Error', 'message': 'An internal server error occurred'}), 500

# ==================== YOLO DETECTION ROUTES ====================

@app.route('/api/detect/ppe', methods=['POST'])
def detect_ppe():
    """Detect PPE from uploaded image or camera frame"""
    try:
        if not init_detection_model() or detection_model is None:
            return jsonify({'success': False, 'error': 'PPE model not loaded'}), 500

        frame = None
        if 'image' in request.files:
            file = request.files['image']
            file_bytes = np.frombuffer(file.read(), np.uint8)
            frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        else:
            payload = request.get_json(silent=True) or {}
            image_b64 = payload.get('image')
            if image_b64:
                try:
                    header, encoded = image_b64.split(',', 1) if ',' in image_b64 else (None, image_b64)
                    img_bytes = base64.b64decode(encoded)
                    frame = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
                except Exception:
                    frame = None

        if frame is None:
            return jsonify({'success': False, 'error': 'No valid image provided'}), 400

        ppe_classes = [
            'Hardhat', None, 'NO-Hardhat', None,
            'NO-Safety Vest', 'Person',
            'Safety Cone', 'Safety Vest',
            'machinery', 'vehicle'
        ]

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = build_color_mask(hsv, CALIBRATED_THRESHOLDS)
        mask = refine_mask(mask, kernel_size=7)

        results = detection_model.predict(
            frame,
            conf=VIOLATION_MODEL_CONF,
            iou=VIOLATION_MODEL_IOU,
            imgsz=VIOLATION_MODEL_IMGSZ,
            verbose=False,
        )

        detections = []
        counts = {
            'hardhat': 0,
            'no_hardhat': 0,
            'safety_vest': 0,
            'no_safety_vest': 0,
            'person': 0,
        }

        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                if cls >= len(ppe_classes):
                    continue
                class_name = ppe_classes[cls]
                if not class_name:
                    continue
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                if class_name == "Safety Vest":
                    area = max(0, x2 - x1) * max(0, y2 - y1)
                    if area < VEST_MIN_BOX_AREA:
                        continue
                    coverage = color_coverage(mask, (x1, y1, x2, y2))
                    if not (conf >= VEST_CONF_STRICT or (conf >= VEST_CONF_SOFT and coverage >= VEST_COLOR_COVERAGE_MIN)):
                        continue
                else:
                    coverage = None

                detections.append({
                    'class': class_name,
                    'confidence': round(conf, 4),
                    'bbox': [x1, y1, x2, y2],
                    'color_coverage': round(coverage, 4) if coverage is not None else None,
                })

                if class_name == 'Hardhat':
                    counts['hardhat'] += 1
                elif class_name == 'NO-Hardhat':
                    counts['no_hardhat'] += 1
                elif class_name == 'Safety Vest':
                    counts['safety_vest'] += 1
                elif class_name == 'NO-Safety Vest':
                    counts['no_safety_vest'] += 1
                elif class_name == 'Person':
                    counts['person'] += 1

        violations = counts['no_hardhat'] + counts['no_safety_vest']
        compliance = 0
        if counts['person'] > 0:
            compliant = max(0, counts['person'] - violations)
            compliance = int(round((compliant / counts['person']) * 100))

        return jsonify({
            'success': True,
            'detections': counts,
            'violations': violations,
            'compliance': compliance,
            'boxes': detections,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detect/fire', methods=['POST'])
def detect_fire_endpoint():
    """Detect fire from video frame"""
    try:
        # This is a placeholder - integrate with actual fire detection model
        return jsonify({
            'success': True,
            'fire_detected': False,
            'confidence': 0.95
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create database if it doesn't exist
    init_db()
    
    # Run Flask app
    # Run Flask app without the automatic reloader to keep a single stable process
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False
    )


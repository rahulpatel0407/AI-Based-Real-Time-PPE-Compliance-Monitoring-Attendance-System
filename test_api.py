#!/usr/bin/env python3
"""
PPE Detection Kit - API Verification Script
Tests all major endpoints to ensure system is operational
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:5000"
SESSION = requests.Session()

# ANSI colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.RESET}")

def test_endpoint(method, endpoint, name, data=None, expected_status=200):
    """Test a single API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            return None
        
        if response.status_code == expected_status:
            print_success(f"{name} ({method} {endpoint}) - Status: {response.status_code}")
            try:
                return response.json()
            except:
                return response.text
        else:
            print_error(f"{name} ({method} {endpoint}) - Status: {response.status_code} (Expected: {expected_status})")
            return None
    except requests.exceptions.ConnectionError:
        print_error(f"Connection Error: Cannot reach {BASE_URL}")
        return None
    except Exception as e:
        print_error(f"{name} - Error: {str(e)}")
        return None

def main():
    print(f"{Colors.BOLD}{Colors.CYAN}PPE DETECTION KIT - API VERIFICATION TEST{Colors.RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base URL: {BASE_URL}")
    
    results = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'endpoints': []
    }
    
    # Test 1: Server Health
    print_header("1. SERVER HEALTH CHECK")
    health_response = test_endpoint("GET", "/api/health", "Health Check", expected_status=200)
    if health_response:
        results['passed'] += 1
        print(f"  Response: {json.dumps(health_response, indent=2)}")
    else:
        results['failed'] += 1
    results['total'] += 1
    
    # Test 2: Authentication
    print_header("2. AUTHENTICATION & LOGIN")
    
    # Test login
    login_data = {"username": "admin", "password": "admin123"}
    login_response = test_endpoint("POST", "/api/login", "Admin Login", login_data)
    results['total'] += 1
    if login_response and 'success' in str(login_response):
        results['passed'] += 1
        print(f"  Response: Login successful, Session created")
    else:
        results['failed'] += 1
        print_error(f"  Response: {login_response}")
    
    # Test verify auth
    verify_response = test_endpoint("GET", "/api/auth/verify", "Verify Authentication", expected_status=200)
    results['total'] += 1
    if verify_response:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 3: Dashboard
    print_header("3. DASHBOARD & DATA")
    
    dashboard_response = test_endpoint("GET", "/api/dashboard", "Dashboard Data", expected_status=200)
    results['total'] += 1
    if dashboard_response:
        results['passed'] += 1
        print(f"  Sections: {', '.join(dashboard_response.keys()) if isinstance(dashboard_response, dict) else 'N/A'}")
    else:
        results['failed'] += 1
    
    # Test 4: Video Streaming
    print_header("4. VIDEO STREAMING")
    
    video_status = test_endpoint("GET", "/api/video/status", "Video Stream Status", expected_status=200)
    results['total'] += 1
    if video_status:
        results['passed'] += 1
        print(f"  Response: {json.dumps(video_status, indent=2)}")
    else:
        results['failed'] += 1
    
    # Test 5: Employees & Attendance
    print_header("5. EMPLOYEE DATA")
    
    employees_response = test_endpoint("GET", "/api/employees", "Get Employees", expected_status=200)
    results['total'] += 1
    if employees_response:
        results['passed'] += 1
        if isinstance(employees_response, dict) and 'employees' in employees_response:
            print(f"  Total employees: {len(employees_response['employees'])}")
    else:
        results['failed'] += 1
    
    # Test 6: Attendance
    print_header("6. ATTENDANCE RECORDS")
    
    attendance_response = test_endpoint("GET", "/api/attendance", "Get Attendance Records", expected_status=200)
    results['total'] += 1
    if attendance_response:
        results['passed'] += 1
        if isinstance(attendance_response, dict) and 'attendance' in attendance_response:
            print(f"  Total records: {len(attendance_response['attendance'])}")
    else:
        results['failed'] += 1
    
    # Test 7: Alerts
    print_header("7. ALERTS & INCIDENTS")
    
    alerts_response = test_endpoint("GET", "/api/alerts", "Get Alerts", expected_status=200)
    results['total'] += 1
    if alerts_response:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    incidents_response = test_endpoint("GET", "/api/incidents", "Get Incidents", expected_status=200)
    results['total'] += 1
    if incidents_response:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 8: Detection Endpoints
    print_header("8. DETECTION ENDPOINTS")
    
    ppe_response = test_endpoint("POST", "/api/detect/ppe", "PPE Detection Endpoint", expected_status=200)
    results['total'] += 1
    if ppe_response:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    fire_response = test_endpoint("POST", "/api/detect/fire", "Fire Detection Endpoint", expected_status=200)
    results['total'] += 1
    if fire_response:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 9: Frontend Assets
    print_header("9. FRONTEND ASSETS")
    
    try:
        index_response = requests.get(f"{BASE_URL}/", timeout=5)
        if index_response.status_code == 200:
            print_success("Dashboard HTML - Status: 200")
            results['passed'] += 1
        else:
            print_error(f"Dashboard HTML - Status: {index_response.status_code}")
            results['failed'] += 1
    except:
        print_error("Dashboard HTML - Connection Error")
        results['failed'] += 1
    results['total'] += 1
    
    try:
        login_page = requests.get(f"{BASE_URL}/login", timeout=5)
        if login_page.status_code == 200:
            print_success("Login Page - Status: 200")
            results['passed'] += 1
        else:
            print_error(f"Login Page - Status: {login_page.status_code}")
            results['failed'] += 1
    except:
        print_error("Login Page - Connection Error")
        results['failed'] += 1
    results['total'] += 1
    
    # Summary
    print_header("TEST SUMMARY")
    print(f"Total Tests: {results['total']}")
    print(f"{Colors.GREEN}Passed: {results['passed']}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {results['failed']}{Colors.RESET}")
    
    success_rate = (results['passed'] / results['total'] * 100) if results['total'] > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ SYSTEM STATUS: OPERATIONAL{Colors.RESET}")
        return 0
    elif success_rate >= 70:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ SYSTEM STATUS: PARTIALLY OPERATIONAL{Colors.RESET}")
        return 1
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ SYSTEM STATUS: CRITICAL ISSUES{Colors.RESET}")
        return 2

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {str(e)}{Colors.RESET}")
        sys.exit(2)

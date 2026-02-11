#!/usr/bin/env python3
"""
Quick Test Script for Login System
Run this to verify the login system is working correctly
"""

import requests
import json

BASE_URL = 'http://localhost:5000'

def test_login_endpoint():
    """Test the login endpoint"""
    print("\n" + "="*50)
    print("Testing Login Endpoint")
    print("="*50)
    
    # Test valid login
    print("\n✓ Testing valid login (admin/admin123)...")
    response = requests.post(
        f'{BASE_URL}/api/login',
        json={
            'username': 'admin',
            'password': 'admin123',
            'remember': False
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    # Test invalid credentials
    print("\n✗ Testing invalid credentials (admin/wrongpass)...")
    response = requests.post(
        f'{BASE_URL}/api/login',
        json={
            'username': 'admin',
            'password': 'wrongpass'
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_verify_endpoint():
    """Test the verify authentication endpoint"""
    print("\n" + "="*50)
    print("Testing Verify Authentication Endpoint")
    print("="*50)
    
    print("\n✓ Testing without authentication...")
    response = requests.get(f'{BASE_URL}/api/auth/verify')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_login_page():
    """Test if login page is accessible"""
    print("\n" + "="*50)
    print("Testing Login Page Access")
    print("="*50)
    
    print("\n✓ Testing /login route...")
    response = requests.get(f'{BASE_URL}/login')
    print(f"Status: {response.status_code}")
    print(f"Content Length: {len(response.content)} bytes")
    if response.status_code == 200:
        print("✅ Login page is accessible")
    else:
        print("❌ Login page not found")

def test_dashboard_redirect():
    """Test if dashboard redirects to login"""
    print("\n" + "="*50)
    print("Testing Dashboard Redirect")
    print("="*50)
    
    print("\n✓ Testing / route without authentication...")
    response = requests.get(f'{BASE_URL}/', allow_redirects=False)
    print(f"Status: {response.status_code}")
    if response.status_code in [301, 302, 303, 307, 308]:
        print("✅ Properly redirects to login (as expected for unauthenticated)")
    elif 'login' in response.text.lower():
        print("✅ Returns login page content")
    else:
        print("⚠️  Status code indicates possible issue")

if __name__ == '__main__':
    print("\n")
    print("╔" + "="*48 + "╗")
    print("║  PPE Detection Kit - Login System Test Suite  ║")
    print("╚" + "="*48 + "╝")
    
    print("\nMake sure the Flask server is running:")
    print("  python backend.py")
    
    try:
        # Test connectivity
        print("\n\nChecking server connectivity...")
        response = requests.get(f'{BASE_URL}/api/dashboard', timeout=5)
        print(f"✅ Server is reachable (Status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server at http://localhost:5000")
        print("   Make sure Flask is running: python backend.py")
        exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)
    
    # Run tests
    try:
        test_login_page()
        test_login_endpoint()
        test_verify_endpoint()
        test_dashboard_redirect()
        
        print("\n" + "="*50)
        print("✅ All tests completed!")
        print("="*50)
        print("\nNext steps:")
        print("1. Visit http://localhost:5000 in your browser")
        print("2. You should be redirected to the login page")
        print("3. Login with:")
        print("   Username: admin")
        print("   Password: admin123")
        print("4. You should see the dashboard")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        exit(1)

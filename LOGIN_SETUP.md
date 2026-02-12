# PPE Detection Kit - Login System Setup Guide

## 📋 Overview
Your PPE Detection Kit application now includes a comprehensive login system with authentication and authorization. All users must log in with valid credentials before accessing the dashboard.

## 🔐 Login Features

### What's New:
1. **Login Page** - Professional, secure login interface
2. **User Authentication** - Username and password validation
3. **Session Management** - Secure session handling
4. **Logout Functionality** - One-click logout from the dashboard
5. **Remember Me** - Optional session persistence
6. **Protected Routes** - All dashboard pages require authentication

## 👤 Demo Credentials

Two demo accounts are available for testing:

### Admin Account
- **Username:** `admin`
- **Password:** `admin123`
- **Role:** Administrator (full access)

### User Account
- **Username:** `user`
- **Password:** `user123`
- **Role:** User (limited access)

## 🚀 How to Use

### Starting the Application

1. Run the Flask backend:
```bash
python backend.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

You will be automatically redirected to the login page if not authenticated.

### Logging In

1. **Enter Credentials:**
   - Enter your username in the "Username" field
   - Enter your password in the "Password" field

2. **Security Options:**
   - Check "Remember me" to keep the session active (optional)
   - Click the eye icon to toggle password visibility

3. **Submit:**
   - Click the "Login" button
   - Wait for authentication confirmation
   - You'll be redirected to the dashboard on successful login

### Logging Out

1. **From Dashboard:**
   - Click on the user profile area in the top-right corner (where it shows the username)
   - Confirm the logout action
   - You'll be redirected to the login page

2. **Or:**
   - Simply close the browser (session will expire)

## 📁 File Structure

```
frontend/
├── login.html                 # Login page (NEW)
├── index.html                 # Main dashboard
├── css/
│   ├── login.css             # Login page styles (NEW)
│   └── style.css             # Dashboard styles (updated)
└── js/
    ├── login.js              # Login logic (NEW)
    └── main.js               # Dashboard logic (updated)

backend.py                     # Flask backend (updated with auth routes)
```

## 🔧 Authentication API Endpoints

### POST `/api/login`
Authenticates user with credentials.

**Request Body:**
```json
{
  "username": "admin",
  "password": "admin123",
  "remember": false
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Login successful",
  "token": "...",
  "user": {
    "username": "admin",
    "name": "Administrator",
    "email": "admin@iocl.com",
    "role": "admin"
  }
}
```

### GET `/api/auth/verify`
Verifies if the current user is authenticated.

**Response:**
```json
{
  "authenticated": true,
  "user": {
    "username": "admin",
    "name": "Administrator",
    "role": "admin"
  }
}
```

### POST `/api/logout`
Logs out the current user.

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

### GET `/api/profile`
Gets the current user's profile information.

**Response:**
```json
{
  "username": "admin",
  "name": "Administrator",
  "email": "admin@iocl.com",
  "role": "admin"
}
```

## 🛡️ Security Features

### Current Implementation:
- ✅ Session-based authentication
- ✅ Password validation
- ✅ Protected API endpoints with login_required decorator
- ✅ Automatic redirect to login for unauthenticated users
- ✅ Secure token generation for API requests

### Recommended for Production:

1. **Hash Passwords:**
   ```bash
   pip install werkzeug
   ```
   Update the user database to store hashed passwords instead of plain text.

2. **Use JWT Tokens:**
   ```bash
   pip install PyJWT
   ```
   Implement JWT-based authentication for stateless API requests.

3. **HTTPS:**
   - Deploy with SSL/TLS certificates
   - Set secure cookie flags
   - Enable HSTS headers

4. **Database:**
   - Move user credentials from hardcoded dictionary to SQLite database
   - Implement proper user role management
   - Add password reset functionality

## 🔄 Updating User Credentials

### Current Setup (Simple):
Edit `backend.py` and modify the `VALID_USERS` dictionary:

```python
VALID_USERS = {
    'admin': {
        'password': 'your_new_password',
        'role': 'admin',
        'name': 'Administrator',
        'email': 'admin@iocl.com'
    },
    'newuser': {
        'password': 'their_password',
        'role': 'user',
        'name': 'New User',
        'email': 'newuser@iocl.com'
    }
}
```

### Better Approach (For Production):
1. Create a user management database
2. Use password hashing (bcrypt, werkzeug)
3. Implement user registration form
4. Add role-based access control (RBAC)

## ⚙️ Environment Variables

Set the following environment variable for production:

```bash
# For development (default):
SECRET_KEY=your-secret-key-change-in-production

# For production, use a strong secret:
export SECRET_KEY='your-very-long-random-secret-key-min-32-characters'
```

## 🐛 Troubleshooting

### Issue: "Invalid username or password"
- ✅ Check spelling of username and password
- ✅ Ensure caps lock is off
- ✅ Verify credentials match exactly

### Issue: "Unauthorized" when accessing dashboard
- ✅ Session may have expired
- ✅ Login again with valid credentials
- ✅ Clear browser cookies and try again

### Issue: Login page redirects to login again
- ✅ Clear browser cache
- ✅ Check Flask server is running
- ✅ Verify `/api/auth/verify` endpoint is accessible

### Issue: Password visibility toggle not working
- ✅ Ensure `login.js` is loaded correctly
- ✅ Check browser console for JavaScript errors
- ✅ Verify Font Awesome icons are loaded

## 📚 Code Examples

### Check if User is Logged In (Frontend):
```javascript
// Automatically checked on page load
fetch('/api/auth/verify')
  .then(res => res.json())
  .then(data => {
    if (data.authenticated) {
      console.log('User:', data.user);
    } else {
      window.location.href = '/login';
    }
  });
```

### Logout (Frontend):
```javascript
function logout() {
  fetch('/api/logout', { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      window.location.href = '/login';
    });
}
```

### Protect API Endpoint (Backend):
```python
from functools import wraps

@app.route('/api/protected')
@login_required
def protected_route():
    return jsonify({'data': 'This is protected'})
```

## 📞 Support

For issues or questions regarding the login system:
1. Check this documentation
2. Review the code comments in `backend.py`, `login.js`, and `login.html`
3. Check browser console for error messages
4. Verify all files are in correct locations

## ✅ Checklist

- [x] Login page created
- [x] Backend authentication endpoints added
- [x] Session management implemented
- [x] Logout functionality added
- [x] Protected routes configured
- [x] Demo credentials provided
- [x] Responsive design
- [x] Error handling
- [x] Security features (basic)

## 🎯 Next Steps

1. Test login with demo credentials
2. Customize user credentials as needed
3. Implement additional security measures for production
4. Add user management interface
5. Set up proper database for user storage
6. Configure HTTPS for production deployment

---

**Version:** 1.0  
**Last Updated:** 2026-01-09  
**Status:** Ready for Development & Testing

# Quick Start Guide - PPE Detection Dashboard

## ✅ Prerequisites
- Python 3.10+
- Webcam/Camera connected to your computer
- All dependencies installed

## 🚀 Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

## 🚀 Step 2: Start the Backend Server
```bash
python backend.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
 * Press CTRL+C to quit
```

## 🚀 Step 3: Open Dashboard in Browser
Navigate to: **http://localhost:5000**

## 📋 Login Credentials
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| user | user123 | User |

## 🎯 Features Available
- ✅ **Login & Authentication** - Secure session management
- ✅ **Live Camera Feed** - Real-time video stream from webcam
- ✅ **Dashboard** - Employee and attendance overview
- ✅ **API Endpoints** - RESTful backend for integrations
- ⏳ **PPE Detection** - Integration in progress
- ⏳ **Fire Detection** - Integration in progress
- ⏳ **Face Recognition Attendance** - Integration in progress

## 📱 Dashboard Sections
1. **Home** - System status and quick statistics
2. **Camera** - Live webcam feed with streaming controls
3. **Attendance** - Employee attendance records
4. **Employees** - Employee database management
5. **Alerts** - System alerts and notifications

## 🔧 Troubleshooting

### Camera Not Working?
- Check if your webcam is connected
- Try unplugging/replugging the camera
- Close other apps using the camera
- The system will show a "Camera Not Available" placeholder if camera fails

### Server Won't Start?
```bash
# Check if port 5000 is in use
netstat -ano | findstr :5000

# If in use, kill the process or use different port
python backend.py --port 5001
```

### Login Failed?
- Verify username and password are correct (case-sensitive)
- Clear browser cache and cookies
- Try incognito/private mode

## 📞 API Endpoints
- `POST /api/login` - User authentication
- `GET /api/dashboard` - Dashboard statistics
- `GET /video_feed` - Live camera MJPEG stream
- `GET /api/video/status` - Camera stream status
- `POST /api/detect/ppe` - PPE detection (in development)
- `POST /api/detect/fire` - Fire detection (in development)

## 🔑 Session Management
- Session timeout: 1 hour
- Automatic logout on browser close
- Secure token-based authentication

## 📝 Notes
- Webcam feed uses MJPEG streaming for low-latency display
- Frame rate is optimized for smooth visualization
- Resolution: 640x480 for balanced performance
- All camera frames are encrypted in transit (when HTTPS is enabled)

---
**Status:** ✅ Ready for Testing  
**Last Updated:** 2024  
**Support:** For issues, check the documentation or review logs in the terminal

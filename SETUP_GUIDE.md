# IOCL Refinery Safety System - Complete Setup Guide

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Installation](#installation)
3. [Running the System](#running-the-system)
4. [Frontend Dashboard](#frontend-dashboard)
5. [Backend API](#backend-api)
6. [Integration](#integration)
7. [Troubleshooting](#troubleshooting)

---

## 🏭 System Overview

The IOCL Refinery Safety & Attendance System is a comprehensive solution combining:

- **PPE Detection**: Real-time detection of safety equipment (helmets, vests)
- **Fire Detection**: Automatic alerts for fire hazards
- **Face Recognition**: Automated attendance tracking via facial recognition
- **Web Dashboard**: Modern, responsive monitoring interface
- **REST API**: Backend services for data management
- **Real-time Alerts**: Live notifications for critical incidents

### System Architecture
```
┌─────────────────────────────────────────┐
│         Web Frontend (React-like)        │
│    - Dashboard, PPE, Attendance, Alerts  │
└──────────────────┬──────────────────────┘
                   │ HTTP/WebSocket
┌──────────────────▼──────────────────────┐
│      Flask Backend API (Python)          │
│  - Data Management, Authentication       │
└──────────────────┬──────────────────────┘
                   │ SQL
┌──────────────────▼──────────────────────┐
│     SQLite Database                      │
│  - Employees, Attendance, Incidents      │
└─────────────────────────────────────────┘
                   
┌──────────────────────────────────────────┐
│    YOLO & Detection Modules              │
│  - PPE Detection, Fire                   │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│    Face Recognition Module               │
│  - Employee Enrollment, Recognition      │
└──────────────────────────────────────────┘
```

---

## 💻 Installation

### Prerequisites
- **Python**: 3.8 or higher
- **pip**: Package manager
- **Git**: Version control (optional)
- **RAM**: 4GB minimum
- **Storage**: 2GB free space

### Step 1: Clone/Download the Repository
```bash
# Using Git
git clone https://github.com/your-repo/PPE_detection_Kit.git
cd PPE_detection_Kit

# Or download and extract ZIP
```

### Step 2: Create Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

Key dependencies:
- `opencv-python`: Computer vision
- `ultralytics`: YOLO detection
- `face_recognition`: Facial recognition
- `flask`: Web framework
- `streamlit`: Interactive UI
- `pandas`: Data analysis
- `playsound`: Audio alerts

### Step 4: Verify Installation
```bash
python -c "import cv2, ultralytics, flask; print('All dependencies installed!')"
```

---

## 🚀 Running the System

### Option 1: Quick Start (Windows)
```bash
# Run the batch file
start.bat
```

### Option 2: Quick Start (Linux/Mac)
```bash
# Make script executable and run
chmod +x start.sh
./start.sh
```

### Option 3: Manual Start (All Platforms)

**Terminal 1 - Flask Backend:**
```bash
python backend.py
# Backend runs at http://localhost:5000
```

**Terminal 2 - Streamlit App (Optional):**
```bash
streamlit run app1.py
# Streamlit runs at http://localhost:8501
```

---

## 📊 Frontend Dashboard

### Accessing the Dashboard
1. Start the Flask backend
2. Open your browser
3. Navigate to: **http://localhost:5000**

### Dashboard Features

#### 1. Dashboard Page
- Real-time safety metrics
- Active worker count
- PPE compliance percentage
- Hazard alerts
- Live camera feeds
- Recent incident log

#### 2. PPE Compliance Page
- Zone-wise compliance tracking
- Non-compliant worker list
- PPE type breakdown (helmets, vests)
- Alert history

#### 3. Attendance Page
- Face-based check-in/check-out
- Daily attendance summary
- Department-wise filtering
- Attendance records table

#### 4. Alerts & Incidents Page
- Critical fire alerts
- Incident timeline
- Response time tracking
- Status indicators

#### 5. Analytics Page
- Monthly safety statistics
- Incident trend charts
- PPE compliance trends
- Safety score

### UI Features
- **Responsive Design**: Works on desktop, tablet, mobile
- **Real-time Updates**: Automatic refresh every 5 seconds
- **Color-coded Alerts**: Green/Yellow/Red for quick identification
- **Interactive Tables**: Sortable and filterable
- **Mobile-friendly**: Touch-optimized interface

---

## 🔌 Backend API

### Base URL
```
http://localhost:5000
```

### Endpoints Reference

#### Dashboard
```
GET /api/dashboard
Response: {
  "ppe_compliance": 94,
  "active_workers": 247,
  "hazard_alerts": 2,
  "total_employees": 260
}
```

#### Incidents
```
GET /api/incidents
Response: {
  "incidents": [
    {
      "time": "14:45",
      "type": "No PPE Detected",
      "location": "Zone B",
      "status": "Pending"
    }
  ]
}
```

#### PPE Compliance
```
GET /api/ppe-compliance?zone=A
Response: {
  "compliance_summary": {
    "helmets": 96,
    "safety_vests": 94
  },
  "non_compliant": [...]
}
```

#### Attendance
```
GET /api/attendance?date=2024-01-08&department=operations
Response: {
  "present": 234,
  "absent": 13,
  "records": [
    {
      "employee_id": "EMP234",
      "name": "Anil Verma",
      "check_in": "08:15",
      "check_out": "16:45",
      "status": "Present"
    }
  ]
}
```

#### Alerts
```
GET /api/alerts
Response: {
  "alerts": [
    {
      "time": "14:15",
      "type": "Fire Detection",
      "location": "Zone C",
      "severity": "Critical",
      "status": "Resolved"
    }
  ]
}
```

#### Analytics
```
GET /api/analytics
Response: {
  "total_incidents": 12,
  "resolved": 11,
  "avg_response_time": "4.5 min",
  "safety_score": 94,
  "incident_trend": [3, 2, 1, 2, 1, 0, 2]
}
```

### Health Check
```
GET /api/health
Response: {
  "status": "healthy",
  "timestamp": "2024-01-08T14:50:00",
  "version": "1.0.0"
}
```

---

## 🔗 Integration

### Integrating YOLO Detection
```python
from YOLO_Video import video_detection, detect_fire

# In backend.py:
result = video_detection('video.mp4')
# Returns: {
#   'fire_detected': bool,
#   'helmet_detected': bool,
#   'confidence': float
# }
```

### Integrating Face Recognition
```python
from face_recognition_module import recognize_face, enroll_face

# In backend.py:
match, message = recognize_face(frame)
# Returns: (employee_id, name, confidence) or None
```

### Integrating Database
```python
from database import get_attendance_report, mark_attendance

# In backend.py:
report = get_attendance_report('2024-01-08', '2024-01-08')
# Returns: Attendance records for the date range
```

### Connecting Camera Streams
Edit `config.json`:
```json
{
  "cameras": [
    {
      "id": "CAM-A1",
      "location": "Zone A",
      "stream_url": "http://camera-ip:8080/stream"
    }
  ]
}
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Find process using port 5000
netstat -ano | findstr :5000  # Windows
lsof -i :5000  # Linux/Mac

# Kill the process
taskkill /PID <PID> /F  # Windows
kill -9 <PID>  # Linux/Mac
```

### Dependencies Not Installing
```bash
# Upgrade pip
pip install --upgrade pip

# Install specific versions
pip install opencv-python==4.5.2
pip install ultralytics==8.0.0
```

### Database Issues
```bash
# Reset database
python -c "from database import init_db; init_db()"

# Check database
sqlite3 attendance.db "SELECT COUNT(*) FROM employees;"
```

### Frontend Not Loading
```bash
# Clear browser cache (Ctrl+Shift+Delete)
# Check console errors (F12)
# Verify backend is running
curl http://localhost:5000/api/health
```

### Face Recognition Issues
```bash
# Verify dlib installation
python -c "import dlib; print('dlib OK')"

# Test face recognition
python -c "import face_recognition; print('face_recognition OK')"
```

### YOLO Model Issues
```bash
# Download model manually
from ultralytics import YOLO
model = YOLO('YOLO-Weights/ppe.pt')

# Check model file
ls -lh YOLO-Weights/
```

---

## 📁 Directory Structure
```
PPE_detection_Kit/
├── frontend/
│   ├── index.html          # Main dashboard
│   ├── css/
│   │   └── style.css       # Styling
│   └── js/
│       └── main.js         # JavaScript logic
├── backend.py              # Flask API
├── database.py             # Database functions
├── YOLO_Video.py           # Detection logic
├── fire_alarm.py           # Alarm system
├── face_recognition_module.py  # Face detection
├── app1.py                 # Streamlit app
├── config.json             # Configuration
├── requirements.txt        # Dependencies
├── start.bat              # Windows launcher
└── start.sh               # Linux/Mac launcher
```

---

## 🔐 Security Considerations

### For Production:
1. **Enable HTTPS**
   ```python
   app.run(ssl_context='adhoc')
   ```

2. **Add Authentication**
   ```python
   from flask_jwt_extended import JWTManager
   jwt = JWTManager(app)
   ```

3. **Rate Limiting**
   ```python
   from flask_limiter import Limiter
   limiter = Limiter(app)
   ```

4. **Environment Variables**
   ```bash
   export FLASK_ENV=production
   export SECRET_KEY=your-secret-key
   ```

5. **Data Encryption**
   - Store sensitive data encrypted
   - Use HTTPS for all communications

---

## 📈 Performance Optimization

- **Caching**: API responses cached for 30 seconds
- **Database Indexing**: Added on frequently queried fields
- **Frontend Optimization**: Lazy loading of images/videos
- **Async Operations**: Background tasks for processing

---

## 📞 Support & Documentation

- **API Documentation**: See IOCL_DASHBOARD_README.md
- **Configuration**: Edit config.json
- **Logs**: Check logs/ directory
- **Issues**: Check GitHub issues or contact support

---

## 📝 Version History

### v2.0.0 (Current)
- Added creative web dashboard
- Flask backend API
- Integration with detection systems
- Real-time alerts
- Analytics module

### v1.0.0
- PPE detection
- Fire detection
- Face recognition
- Attendance tracking

---

## 📄 License
MIT License - See LICENSE file

---

## 👥 Contributors
Indian Oil Corporation Limited - Safety Team

---

**Last Updated**: January 8, 2026

# IOCL Refinery Safety & Attendance System - Web Interface

## Overview
A modern, creative web application for comprehensive safety monitoring, PPE compliance tracking, and employee attendance management for IOCL refineries.

## Features

### 1. Dashboard
- Real-time safety status monitoring
- PPE compliance metrics (94%+)
- Active worker count
- Hazard alerts and incidents
- Live camera feeds
- Recent incident log

### 2. PPE Compliance Module
- Zone-based PPE monitoring
- Real-time compliance percentage tracking
- Non-compliant worker identification
- Helmet and Safety Vest tracking
- Alert history and warnings

### 3. Attendance & Face Recognition
- Face-based attendance tracking
- Real-time employee check-in/check-out
- Department-wise attendance reports
- Absence notifications
- Attendance history with timestamps

### 4. Safety Alerts & Incidents
- Real-time fire detection alerts
- Critical incident tracking
- Response time monitoring
- Historical incident logs

### 5. Analytics & Reports
- Monthly safety statistics
- Incident trend analysis
- PPE compliance trends
- Safety score tracking
- Downloadable reports

## Frontend Architecture

```
frontend/
├── index.html          # Main dashboard
├── css/
│   └── style.css      # Responsive styling
└── js/
    └── main.js        # Client-side logic
```

### Key Technologies
- **HTML5**: Semantic markup
- **CSS3**: Responsive grid and flexbox layouts
- **JavaScript**: Vanilla JS (no dependencies)
- **Font Awesome 6**: Icon library
- **Responsive Design**: Works on desktop, tablet, mobile

## Backend API

### Base URL
```
http://localhost:5000
```

### Endpoints

#### Dashboard
- `GET /api/dashboard` - Get dashboard metrics
- `GET /api/incidents` - Get recent incidents

#### PPE Compliance
- `GET /api/ppe-compliance` - Get PPE compliance data
- `GET /api/ppe-compliance?zone=A` - Filter by zone

#### Attendance
- `GET /api/attendance` - Get attendance records
- `GET /api/attendance?date=2024-01-08` - Filter by date
- `GET /api/attendance?department=operations` - Filter by department

#### Alerts
- `GET /api/alerts` - Get all alerts

#### Analytics
- `GET /api/analytics` - Get analytics data
- `GET /api/analytics?month=01&year=2024` - Filter by month/year

#### Employee Management
- `GET /api/employees` - Get all employees
- `GET /api/employee/<id>` - Get employee details

#### Refinery Operations
- `GET /api/zones` - Get zone information
- `GET /api/camera-feeds` - Get camera feed status
- `GET /api/health` - Health check

## Running the Application

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Flask Backend
```bash
python backend.py
```
The backend will run on `http://localhost:5000`

### 3. Access the Dashboard
Open your browser and navigate to:
```
http://localhost:5000
```

## API Response Examples

### Dashboard Data
```json
{
  "ppe_compliance": 94,
  "active_workers": 247,
  "hazard_alerts": 2,
  "total_employees": 260
}
```

### Attendance Data
```json
{
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

### Alerts Data
```json
{
  "alerts": [
    {
      "time": "14:15",
      "type": "Fire Detection",
      "location": "Zone C",
      "severity": "Critical",
      "response_time": "2 min",
      "status": "Resolved"
    }
  ]
}
```

## Real-time Features

### Polling Updates
- Dashboard updates every 5 seconds
- Alerts update every 3 seconds

### WebSocket (Optional)
For real-time updates without polling:
```javascript
const ws = new WebSocket('ws://localhost:5000/ws');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Handle real-time data
};
```

## User Interface Sections

### Navigation
- **Top Navbar**: Main navigation menu and user profile
- **Sidebar**: Quick access to all modules

### Dashboard Cards
- Status indicators with color coding
- Green: Operational/Safe
- Yellow: Caution
- Blue: Information
- Red: Critical/Danger

### Alert System
- Critical alerts appear at top of page
- Auto-dismiss after 5 seconds
- Color-coded by severity

## Customization

### Colors
Edit `/frontend/css/style.css` CSS variables:
```css
:root {
    --primary-color: #1e40af;
    --secondary-color: #dc2626;
    --warning-color: #f59e0b;
    --success-color: #10b981;
}
```

### API Endpoints
Modify `/backend.py` to integrate with your actual systems

### Data Refresh Rate
Adjust in `/frontend/js/main.js`:
```javascript
setInterval(() => updateDashboard(), 5000); // 5 seconds
```

## Integration with Existing Systems

### Connect to YOLO Detection
```python
from YOLO_Video import video_detection, detect_fire
# Use video_detection results in API responses
```

### Connect to Face Recognition
```python
from face_recognition_module import recognize_face
# Use face data in attendance endpoints
```

### Connect to Database
```python
from database import get_attendance_report, get_all_employees
# Query existing SQLite database
```

## Performance Considerations

- **Client-side caching**: API results cached in browser
- **Lazy loading**: Pages loaded on-demand
- **Efficient queries**: SQL optimized for large datasets
- **Responsive images**: Optimized for all screen sizes

## Browser Support

- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- Mobile browsers: ✅ Responsive design

## Security Considerations

- Add authentication (JWT tokens)
- Implement HTTPS in production
- Add rate limiting to API endpoints
- Validate all input data
- Use environment variables for configuration

## Future Enhancements

- [ ] WebSocket for real-time updates
- [ ] Advanced analytics with charts (Chart.js)
- [ ] Mobile app (React Native)
- [ ] Email/SMS alerts
- [ ] Machine learning predictions
- [ ] Multi-language support
- [ ] Role-based access control
- [ ] Audit logging

## Troubleshooting

### API not responding
- Check if Flask backend is running: `python backend.py`
- Verify port 5000 is not in use
- Check firewall settings

### Data not loading
- Check browser console for errors (F12)
- Verify API endpoints in network tab
- Check database connection

### UI not responsive
- Clear browser cache (Ctrl+Shift+Delete)
- Check CSS file is loaded
- Verify JavaScript is enabled

## Support
For issues or feature requests, contact the development team.

## License
MIT License - See LICENSE file for details

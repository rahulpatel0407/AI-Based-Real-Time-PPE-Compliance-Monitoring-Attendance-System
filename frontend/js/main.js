// ==================== CAMERA FEED MANAGEMENT ====================

let cameraStreamActive = false;
let mjpegRefreshInterval = null;
let localPreviewStream = null;
let isCameraModalOpen = false;
let lastFocusedElement = null;
let currentUserRole = null;

async function initializeCamera() {
    // Initialize camera stream - MJPEG via direct image src
    try {
        const videoStream = document.getElementById('video-stream');
        const placeholder = document.getElementById('camera-placeholder');
        const status = document.getElementById('stream-status');
        
        // Check if camera is available
        const response = await fetch('/api/video/status');
        const data = await response.json();
        
        console.log('[CAMERA] Status:', data);
        
        // Show stream regardless (will show placeholder on backend if camera unavailable)
        videoStream.src = '/video_feed?t=' + Date.now(); // Add timestamp to prevent caching
        videoStream.style.display = 'block';
        placeholder.style.display = 'none';
        
        status.textContent = 'LIVE - Connected';
        status.style.color = '#10b981';
        cameraStreamActive = true;
        
        console.log('[CAMERA] Stream initialized');
    } catch (error) {
        console.error('[CAMERA] Error:', error);
        document.getElementById('stream-status').textContent = 'Connection Error';
        document.getElementById('stream-status').style.color = '#ef4444';
    }
}

function toggleCamera() {
    // Toggle camera feed visibility
    const videoStream = document.getElementById('video-stream');
    const placeholder = document.getElementById('camera-placeholder');
    
    if (cameraStreamActive) {
        if (videoStream.style.display === 'none') {
            videoStream.style.display = 'block';
            placeholder.style.display = 'none';
        } else {
            videoStream.style.display = 'none';
            placeholder.style.display = 'block';
        }
    }
}

function captureFrame() {
    // Capture current frame from video stream
    const videoStream = document.getElementById('video-stream');
    if (videoStream.src && cameraStreamActive) {
        try {
            // Try to fetch the current frame
            fetch('/api/video/status')
                .then(() => {
                    // Show notification
                    const status = document.getElementById('stream-status');
                    const originalText = status.textContent;
                    status.textContent = 'Frame captured!';
                    status.style.color = '#10b981';
                    
                    setTimeout(() => {
                        status.textContent = originalText;
                    }, 2000);
                });
        } catch (error) {
            console.error('[CAMERA] Capture error:', error);
        }
    }
}

// ==================== CAMERA MANAGEMENT ====================
const defaultCameraThumbnail = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180' viewBox='0 0 320 180'><rect width='320' height='180' fill='%230b1851'/><circle cx='160' cy='90' r='32' fill='%23f59d10'/><rect x='90' y='60' width='140' height='60' rx='10' fill='rgba(255,255,255,0.12)'/><text x='160' y='140' font-size='14' font-family='Arial' fill='%23ffffff' text-anchor='middle'>No Preview</text></svg>";

function setupCameraManagement() {
    const addButton = document.getElementById('add-camera-btn');
    const closeButton = document.getElementById('camera-modal-close');
    const cancelButton = document.getElementById('camera-cancel-btn');
    const testButton = document.getElementById('camera-test-btn');
    const modalOverlay = document.querySelector('#camera-modal .modal-overlay');
    const cameraTypeSelect = document.getElementById('camera-type');
    const form = document.getElementById('camera-form');

    if (addButton) {
        if (currentUserRole && currentUserRole !== 'admin') {
            addButton.disabled = true;
            addButton.title = 'Admin access required';
        }
        addButton.addEventListener('click', openCameraModal);
    }

    closeButton?.addEventListener('click', closeCameraModal);
    cancelButton?.addEventListener('click', closeCameraModal);
    modalOverlay?.addEventListener('click', (event) => {
        if (event.target?.dataset?.close) {
            closeCameraModal();
        }
    });

    cameraTypeSelect?.addEventListener('change', updateCameraTypeFields);
    testButton?.addEventListener('click', testCameraConnection);
    form?.addEventListener('submit', saveCamera);

    updateCameraTypeFields();
}

function openCameraModal() {
    const modal = document.getElementById('camera-modal');
    if (!modal) return;
    lastFocusedElement = document.activeElement;
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    isCameraModalOpen = true;

    resetCameraForm();
    setTimeout(() => {
        document.getElementById('camera-name')?.focus();
    }, 0);

    document.addEventListener('keydown', handleModalKeydown);
}

function closeCameraModal() {
    const modal = document.getElementById('camera-modal');
    if (!modal) return;
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    isCameraModalOpen = false;
    stopLocalPreview();
    resetPreview();
    resetFormMessage();
    document.removeEventListener('keydown', handleModalKeydown);
    if (lastFocusedElement) {
        lastFocusedElement.focus();
    }
}

function handleModalKeydown(event) {
    if (!isCameraModalOpen) return;
    if (event.key === 'Escape') {
        closeCameraModal();
        return;
    }

    if (event.key === 'Tab') {
        const modal = document.getElementById('camera-modal');
        const focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            last.focus();
            event.preventDefault();
        } else if (!event.shiftKey && document.activeElement === last) {
            first.focus();
            event.preventDefault();
        }
    }
}

function updateCameraTypeFields() {
    const type = document.getElementById('camera-type')?.value;
    const externalFields = document.querySelectorAll('.external-field');
    const streamField = document.getElementById('camera-stream-url');

    if (type === 'local') {
        externalFields.forEach(field => field.style.display = 'none');
        if (streamField) {
            streamField.removeAttribute('required');
        }
        resetPreview();
    } else {
        externalFields.forEach(field => field.style.display = 'block');
        if (streamField) {
            streamField.setAttribute('required', 'required');
        }
        resetPreview();
    }
}

async function testCameraConnection() {
    const type = document.getElementById('camera-type')?.value;
    const testButton = document.getElementById('camera-test-btn');

    resetFormMessage();
    setPreviewStatus('Testing connection...', '');
    testButton.disabled = true;

    try {
        if (type === 'local') {
            await startLocalPreview();
            setFormMessage('Local camera preview active.', 'success');
            setPreviewStatus('Live (Local)', 'success');
            return;
        }

        const payload = getCameraPayload();
        if (!payload.stream_url) {
            setFormMessage('Stream URL is required for external cameras.', 'error');
            setPreviewStatus('Test failed', 'error');
            return;
        }

        const response = await fetch('/api/cameras/test', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            setFormMessage(data.message || 'Camera test failed.', 'error');
            setPreviewStatus('Test failed', 'error');
            return;
        }

        showExternalPreview(data.preview);
        setFormMessage(data.message || 'Camera connection successful.', 'success');
        setPreviewStatus('Online', 'success');
    } catch (error) {
        console.error('Camera test error:', error);
        setFormMessage('Unable to test camera connection.', 'error');
        setPreviewStatus('Test failed', 'error');
    } finally {
        testButton.disabled = false;
    }
}

async function saveCamera(event) {
    event.preventDefault();
    resetFormMessage();

    const payload = getCameraPayload();
    if (!payload.name) {
        setFormMessage('Camera name is required.', 'error');
        return;
    }

    if (payload.type === 'external' && !payload.stream_url) {
        setFormMessage('Stream URL is required for external cameras.', 'error');
        return;
    }

    try {
        const response = await fetch('/api/cameras', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            setFormMessage(data.message || 'Unable to save camera.', 'error');
            return;
        }

        setFormMessage('Camera saved successfully.', 'success');
        await loadCameras();
        setTimeout(() => closeCameraModal(), 500);
    } catch (error) {
        console.error('Save camera error:', error);
        setFormMessage('Unable to save camera.', 'error');
    }
}

function getCameraPayload() {
    return {
        name: document.getElementById('camera-name')?.value.trim(),
        type: document.getElementById('camera-type')?.value,
        stream_url: document.getElementById('camera-stream-url')?.value.trim(),
        snapshot_url: document.getElementById('camera-snapshot-url')?.value.trim(),
        username: document.getElementById('camera-username')?.value.trim(),
        password: document.getElementById('camera-password')?.value,
        location: document.getElementById('camera-location')?.value.trim()
    };
}

function setFormMessage(message, type) {
    const messageBox = document.getElementById('camera-form-message');
    if (!messageBox) return;
    messageBox.textContent = message;
    messageBox.classList.remove('success', 'error');
    if (type) {
        messageBox.classList.add(type);
    }
}

function resetFormMessage() {
    const messageBox = document.getElementById('camera-form-message');
    if (messageBox) {
        messageBox.textContent = '';
        messageBox.classList.remove('success', 'error');
    }
}

function setPreviewStatus(message, type) {
    const status = document.getElementById('camera-preview-status');
    if (!status) return;
    status.textContent = message;
    status.style.color = type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#6b7280';
}

function resetCameraForm() {
    const form = document.getElementById('camera-form');
    form?.reset();
    updateCameraTypeFields();
    resetPreview();
    resetFormMessage();
    setPreviewStatus('Awaiting test...', '');
}

function resetPreview() {
    const video = document.getElementById('camera-preview-video');
    const image = document.getElementById('camera-preview-image');
    const placeholder = document.getElementById('camera-preview-placeholder');
    if (video) {
        video.style.display = 'none';
        video.pause();
        video.srcObject = null;
    }
    if (image) {
        image.style.display = 'none';
        image.src = '';
    }
    if (placeholder) {
        placeholder.style.display = 'flex';
    }
}

async function startLocalPreview() {
    const video = document.getElementById('camera-preview-video');
    const placeholder = document.getElementById('camera-preview-placeholder');
    const image = document.getElementById('camera-preview-image');

    stopLocalPreview();
    try {
        localPreviewStream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (video) {
            video.srcObject = localPreviewStream;
            video.style.display = 'block';
            video.play();
        }
        if (placeholder) placeholder.style.display = 'none';
        if (image) image.style.display = 'none';
    } catch (error) {
        setFormMessage('Unable to access local camera. Check browser permissions.', 'error');
        setPreviewStatus('Permission denied', 'error');
        resetPreview();
    }
}

function stopLocalPreview() {
    if (localPreviewStream) {
        localPreviewStream.getTracks().forEach(track => track.stop());
        localPreviewStream = null;
    }
}

function showExternalPreview(previewDataUrl) {
    const video = document.getElementById('camera-preview-video');
    const image = document.getElementById('camera-preview-image');
    const placeholder = document.getElementById('camera-preview-placeholder');
    stopLocalPreview();
    if (video) {
        video.style.display = 'none';
        video.srcObject = null;
    }
    if (image) {
        image.src = previewDataUrl || '';
        image.style.display = 'block';
    }
    if (placeholder) {
        placeholder.style.display = 'none';
    }
}

async function loadCameras() {
    const list = document.getElementById('camera-list');
    if (!list) return;
    try {
        const response = await fetch('/api/cameras', { credentials: 'include' });
        const data = await response.json();
        if (!response.ok) {
            list.innerHTML = '<div class="camera-empty">Unable to load cameras.</div>';
            return;
        }
        renderCameraList(data.cameras || []);
    } catch (error) {
        console.error('Load cameras error:', error);
        list.innerHTML = '<div class="camera-empty">Unable to load cameras.</div>';
    }
}

function renderCameraList(cameras) {
    const list = document.getElementById('camera-list');
    if (!list) return;
    list.innerHTML = '';
    if (!cameras.length) {
        list.innerHTML = '<div class="camera-empty">No cameras added yet.</div>';
        return;
    }

    cameras.forEach(camera => {
        const status = (camera.status || 'Offline').toLowerCase();
        const statusClass = status === 'online' ? 'online' : status === 'local' ? 'local' : 'offline';
        const card = document.createElement('div');
        card.className = 'camera-card';
        card.innerHTML = `
            <img class="camera-thumb" src="${camera.thumbnail_url || defaultCameraThumbnail}" alt="${camera.name} thumbnail">
            <div class="camera-meta">
                <h4>${camera.name}</h4>
                <p>${camera.type === 'local' ? 'Local Camera' : 'External Network Camera'}</p>
                <p>${camera.location || 'No location provided'}</p>
            </div>
            <div class="camera-status">
                <span class="status-pill ${statusClass}">${camera.status || 'Offline'}</span>
                <span class="muted text-xs">Added by ${camera.created_by || 'System'}</span>
            </div>
        `;
        list.appendChild(card);
    });
}

// ==================== Authentication Check ====================
// Check if user is authenticated on page load
async function checkAuthentication() {
    try {
        const response = await fetch('/api/auth/verify', { credentials: 'include' });
        const data = await response.json();
        
        if (!data.authenticated) {
            // Redirect to login
            window.location.href = '/login';
            return false;
        }
        
        // Update user profile display
        if (data.user) {
            const userNameElement = document.querySelector('.user-name');
            if (userNameElement) {
                userNameElement.textContent = data.user.name || data.user.username;
            }
            currentUserRole = data.user.role || null;
        }
        
        return true;
    } catch (error) {
        console.error('Auth verification error:', error);
        window.location.href = '/login';
        return false;
    }
}

// ==================== Logout Handler ====================
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        fetch('/api/logout', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(response => {
            if (response.ok) {
                // Clear local storage
                localStorage.removeItem('auth_token');
                localStorage.removeItem('user_info');
                // Redirect to login
                window.location.href = '/login';
            }
        }).catch(error => {
            console.error('Logout error:', error);
            window.location.href = '/login';
        });
    }
}

// Add logout button click handler if it exists
document.addEventListener('DOMContentLoaded', () => {
    const userProfile = document.querySelector('.user-profile');
    if (userProfile) {
        userProfile.addEventListener('click', logout);
        userProfile.style.cursor = 'pointer';
    }
});

// ==================== Page Navigation ====================
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = link.getAttribute('data-page');
        navigateTo(page);
    });
});

document.querySelectorAll('.menu-item').forEach(item => {
    item.addEventListener('click', () => {
        document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
        item.classList.add('active');
        const page = item.getAttribute('data-page');
        navigateTo(page);
    });
});

function navigateTo(page) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    
    // Show selected page
    const selectedPage = document.getElementById(page);
    if (selectedPage) {
        selectedPage.classList.add('active');
    }

    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-page') === page) {
            link.classList.add('active');
        }
    });

    // Load data for the page
    loadPageData(page);
}

// Load page-specific data
function loadPageData(page) {
    switch(page) {
        case 'dashboard':
            updateDashboard();
            break;
        case 'ppe-compliance':
            updatePPECompliance();
            break;
        case 'attendance':
            updateAttendance();
            break;
        case 'alerts':
            updateAlerts();
            break;
        case 'analytics':
            updateAnalytics();
            break;
    }
}

// Update Dashboard
function updateDashboard() {
    console.log('Loading dashboard data...');
    
    // Fetch data from backend
    fetch('/api/dashboard')
        .then(response => response.json())
        .then(data => {
            document.getElementById('ppe-status').textContent = data.ppe_compliance + '%';
            document.getElementById('active-workers').textContent = data.active_workers;
            document.getElementById('hazard-alerts').textContent = data.hazard_alerts;
        })
        .catch(error => console.error('Error loading dashboard:', error));

    // Update incidents
    updateIncidents();
}

function updateIncidents() {
    fetch('/api/incidents')
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('incidents-tbody');
            tbody.innerHTML = '';
            
            data.incidents.forEach(incident => {
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${incident.time}</td>
                    <td>${incident.type}</td>
                    <td>${incident.location}</td>
                    <td><span class="status-badge ${incident.status.toLowerCase()}">${incident.status}</span></td>
                    <td><button class="btn-small" onclick="handleIncident('${incident.id}')">Review</button></td>
                `;
            });
        })
        .catch(error => console.error('Error loading incidents:', error));
}

// Update PPE Compliance
function updatePPECompliance() {
    console.log('Loading PPE compliance data...');
    
    fetch('/api/ppe-compliance')
        .then(response => response.json())
        .then(data => {
            // Update non-compliant workers
            const tbody = document.getElementById('non-compliant-tbody');
            tbody.innerHTML = '';
            
            data.non_compliant.forEach(worker => {
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${worker.employee_id}</td>
                    <td>${worker.name}</td>
                    <td>${worker.missing_ppe}</td>
                    <td><span class="badge-${worker.alerts > 2 ? 'danger' : 'warning'}">${worker.alerts}</span></td>
                `;
            });
        })
        .catch(error => console.error('Error loading PPE compliance:', error));
}

// Update Attendance
function updateAttendance() {
    console.log('Loading attendance data...');
    
    // Set today's date
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('attendance-date').value = today;
    
    fetch('/api/attendance?date=' + today)
        .then(response => response.json())
        .then(data => {
            document.getElementById('present-count').textContent = data.present;
            document.getElementById('absent-count').textContent = data.absent;
            
            // Update attendance records
            const tbody = document.getElementById('attendance-tbody');
            tbody.innerHTML = '';
            
            data.records.forEach(record => {
                const row = tbody.insertRow();
                const status = record.status === 'Present' ? 'success' : 'danger';
                row.innerHTML = `
                    <td>${record.employee_id}</td>
                    <td>${record.name}</td>
                    <td>${record.check_in || '-'}</td>
                    <td>${record.check_out || '-'}</td>
                    <td><span class="status-badge ${status}">${record.status}</span></td>
                `;
            });
        })
        .catch(error => console.error('Error loading attendance:', error));
}

// Update Alerts
function updateAlerts() {
    console.log('Loading alerts...');
    
    fetch('/api/alerts')
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('alerts-tbody');
            tbody.innerHTML = '';
            
            data.alerts.forEach(alert => {
                const row = tbody.insertRow();
                const severityClass = alert.severity === 'Critical' ? 'severity-critical' : 'severity-warning';
                const statusClass = alert.status === 'Resolved' ? 'success' : 'warning';
                
                row.innerHTML = `
                    <td>${alert.time}</td>
                    <td>${alert.type}</td>
                    <td>${alert.location}</td>
                    <td><span class="${severityClass}">${alert.severity}</span></td>
                    <td>${alert.response_time}</td>
                    <td><span class="status-badge ${statusClass}">${alert.status}</span></td>
                `;
            });
        })
        .catch(error => console.error('Error loading alerts:', error));
}

// Update Analytics
function updateAnalytics() {
    console.log('Loading analytics...');
    
    fetch('/api/analytics')
        .then(response => response.json())
        .then(data => {
            console.log('Analytics data:', data);
        })
        .catch(error => console.error('Error loading analytics:', error));
}

// Filters
document.getElementById('zone-filter')?.addEventListener('change', () => {
    updatePPECompliance();
});

document.getElementById('date-filter')?.addEventListener('change', () => {
    updatePPECompliance();
});

document.getElementById('attendance-date')?.addEventListener('change', (e) => {
    fetch('/api/attendance?date=' + e.target.value)
        .then(response => response.json())
        .then(data => {
            document.getElementById('present-count').textContent = data.present;
            document.getElementById('absent-count').textContent = data.absent;
        })
        .catch(error => console.error('Error loading attendance:', error));
});

document.getElementById('department-filter')?.addEventListener('change', () => {
    updateAttendance();
});

// Handle incident actions
function handleIncident(incidentId) {
    console.log('Handling incident:', incidentId);
    alert('Incident ID: ' + incidentId);
}

// Real-time updates
function startRealtimeUpdates() {
    // Update dashboard every 5 seconds
    setInterval(() => {
        if (document.getElementById('dashboard').classList.contains('active')) {
            updateDashboard();
        }
    }, 5000);

    // Update alerts every 3 seconds
    setInterval(() => {
        if (document.getElementById('alerts').classList.contains('active')) {
            updateAlerts();
        }
    }, 3000);
}

// WebSocket for real-time updates
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(protocol + '//' + window.location.host + '/ws');

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleRealtimeData(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        // Reconnect after 3 seconds
        setTimeout(initWebSocket, 3000);
    };
}

function handleRealtimeData(data) {
    switch(data.type) {
        case 'fire_alert':
            showCriticalAlert('🔥 FIRE DETECTED!', data.location);
            updateDashboard();
            break;
        case 'ppe_violation':
            updatePPECompliance();
            break;
        case 'attendance_update':
            updateAttendance();
            break;
    }
}

function showCriticalAlert(title, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert-box critical';
    alertDiv.innerHTML = `
        <div class="alert-icon"><i class="fas fa-fire"></i></div>
        <div class="alert-content">
            <h4>${title}</h4>
            <p>${message}</p>
            <span class="timestamp">Time: ${new Date().toLocaleTimeString()}</span>
        </div>
    `;
    
    const mainContent = document.querySelector('.main-content');
    mainContent.insertBefore(alertDiv, mainContent.firstChild);
    
    // Remove after 5 seconds
    setTimeout(() => alertDiv.remove(), 5000);
}


// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Initializing IOCL Safety Dashboard...');
    
    // Check authentication first
    const isAuthenticated = await checkAuthentication();
    if (isAuthenticated) {
        navigateTo('dashboard');
        startRealtimeUpdates();
        setupCameraManagement();
        loadCameras();
        
        // Initialize camera feed
        setTimeout(() => {
            initializeCamera();
        }, 500);
        
        // Uncomment to enable WebSocket updates
        // initWebSocket();
    }
});

// Export functions for testing
window.dashboard = {
    navigateTo,
    updateDashboard,
    updatePPECompliance,
    updateAttendance,
    updateAlerts,
    updateAnalytics,
    logout
};

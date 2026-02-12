/**
 * IOCL Refinery Safety & Monitoring System
 * Professional JavaScript Application
 * Version: 2.0
 */

'use strict';

// ==================== Configuration ====================
const CONFIG = {
    apiBaseUrl: window.location.origin,
    refreshInterval: 5000,
    cameraFeedUrl: '/video_feed',
    enableWebSocket: false,
    enableDebug: false,
    violationSnapshotLimit: 6,
    violationPageSize: 12
};

// ==================== State Management ====================
const AppState = {
    currentPage: 'home',
    isAuthenticated: false,
    cameraActive: false,
    userData: null
};

// ==================== Utility Functions ====================
const Utils = {
    log: (...args) => {
        if (CONFIG.enableDebug) {
            console.log('[IOCL App]', ...args);
        }
    },

    error: (...args) => {
        console.error('[IOCL App Error]', ...args);
    },

    formatTime: (date = new Date()) => {
        return date.toLocaleTimeString('en-IN', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    },

    formatDate: (date = new Date()) => {
        return date.toLocaleDateString('en-IN', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
    },

    formatDateTime: (value) => {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString('en-IN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    },

    debounce: (func, wait) => {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// ==================== API Service ====================
const API = {
    async fetch(endpoint, options = {}) {
        try {
            const url = `${CONFIG.apiBaseUrl}${endpoint}`;
            const response = await fetch(url, {
                credentials: 'include',
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            Utils.error('API fetch error:', error);
            throw error;
        }
    },

    async get(endpoint) {
        return this.fetch(endpoint);
    },

    async post(endpoint, data) {
        return this.fetch(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
};

// ==================== Authentication Module ====================
const Auth = {
    async checkAuth() {
        try {
            const data = await API.get('/api/auth/verify');
            
            if (data.authenticated) {
                AppState.isAuthenticated = true;
                AppState.userData = data.user;
                this.updateUserProfile(data.user);
                if (typeof Camera !== 'undefined' && Camera.applyAccessControl) {
                    Camera.applyAccessControl();
                }
                return true;
            } else {
                this.redirectToLogin();
                return false;
            }
        } catch (error) {
            Utils.error('Authentication check failed:', error);
            return false;
        }
    },

    updateUserProfile(user) {
        const userNameEl = document.querySelector('.user-name');
        if (userNameEl && user) {
            userNameEl.textContent = user.name || user.username || 'Admin';
        }
    },

    async logout() {
        if (!confirm('Are you sure you want to logout?')) {
            return;
        }

        try {
            await API.post('/api/logout', {});
            localStorage.clear();
            this.redirectToLogin();
        } catch (error) {
            Utils.error('Logout error:', error);
            this.redirectToLogin();
        }
    },

    redirectToLogin() {
        window.location.href = '/login';
    }
};

// ==================== Navigation Module ====================
const Navigation = {
    init() {
        // Navigation links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = link.getAttribute('data-page');
                this.navigateTo(page);
            });
        });

        // Mobile toggle
        const mobileToggle = document.querySelector('.mobile-toggle');
        if (mobileToggle) {
            mobileToggle.addEventListener('click', () => {
                const menu = document.querySelector('.navbar-menu');
                menu.classList.toggle('active');
                const isExpanded = menu.classList.contains('active');
                mobileToggle.setAttribute('aria-expanded', isExpanded);
            });
        }

        // User profile handled by profile.js

        // Handle hash navigation
        window.addEventListener('hashchange', () => {
            const hash = window.location.hash.slice(1);
            if (hash) {
                this.navigateTo(hash);
            }
        });
    },

    navigateTo(page) {
        // Hide all pages
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        
        // Show selected page
        const selectedPage = document.getElementById(page);
        if (selectedPage) {
            selectedPage.classList.add('active');
            AppState.currentPage = page;

            // Update URL hash
            window.location.hash = page;

            // Update active navigation
            document.querySelectorAll('.nav-link').forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('data-page') === page) {
                    link.classList.add('active');
                }
            });

            // Close mobile menu
            const menu = document.querySelector('.navbar-menu');
            if (menu) {
                menu.classList.remove('active');
            }

            // Load page data
            this.loadPageData(page);

            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    },

    loadPageData(page) {
        switch(page) {
            case 'dashboard':
                Dashboard.load();
                break;
            case 'ppe-compliance':
                PPE.load();
                break;
            case 'attendance':
                Attendance.load();
                break;
            case 'safety':
            case 'about':
            case 'home':
                // Static pages - no data loading needed
                break;
        }
    }
};

// ==================== Dashboard Module ====================
const Dashboard = {
    updateInterval: null,

    async load() {
        Utils.log('Loading dashboard...');
        await this.updateMetrics();
        await this.updateIncidents();
        Camera.init();
        this.startAutoUpdate();
    },

    async updateMetrics() {
        try {
            const data = await API.get('/api/dashboard');
            
            const ppeStatus = document.getElementById('ppe-status');
            const activeWorkers = document.getElementById('active-workers');
            const hazardAlerts = document.getElementById('hazard-alerts');

            if (ppeStatus) ppeStatus.textContent = `${data.ppe_compliance || 94.2}%`;
            if (activeWorkers) activeWorkers.textContent = data.active_workers || 247;
            if (hazardAlerts) hazardAlerts.textContent = data.hazard_alerts || 2;
        } catch (error) {
            Utils.error('Failed to update dashboard metrics:', error);
        }
    },

    async updateIncidents() {
        try {
            const data = await API.get('/api/incidents');
            const tbody = document.getElementById('incidents-tbody');
            
            if (!tbody || !data.incidents) return;

            tbody.innerHTML = data.incidents.map(incident => `
                <tr>
                    <td>${incident.time || '-'}</td>
                    <td><i class="fas fa-${this.getIncidentIcon(incident.type)}"></i> ${incident.type || 'Unknown'}</td>
                    <td>${incident.location || '-'}</td>
                    <td><span class="badge badge-${this.getSeverityClass(incident.severity)}">${incident.severity || 'Medium'}</span></td>
                    <td><span class="badge badge-${this.getStatusClass(incident.status)}">${incident.status || 'Pending'}</span></td>
                    <td><button class="btn btn-sm btn-primary" onclick="Dashboard.viewIncident('${incident.id}')">Review</button></td>
                </tr>
            `).join('');
        } catch (error) {
            Utils.error('Failed to update incidents:', error);
        }
    },

    getIncidentIcon(type) {
        const icons = {
            'PPE Violation': 'hard-hat',
            'Fire Alert': 'fire',
            'default': 'exclamation-triangle'
        };
        return icons[type] || icons.default;
    },

    getSeverityClass(severity) {
        const classes = {
            'Critical': 'danger',
            'High': 'danger',
            'Medium': 'warning',
            'Low': 'info'
        };
        return classes[severity] || 'info';
    },

    getStatusClass(status) {
        const classes = {
            'Resolved': 'success',
            'Pending': 'info',
            'In Progress': 'warning',
            'Critical': 'danger'
        };
        return classes[status] || 'info';
    },

    viewIncident(id) {
        Utils.log('Viewing incident:', id);
        alert(`Incident ID: ${id}\n\nDetails would be shown in a modal.`);
    },

    startAutoUpdate() {
        this.stopAutoUpdate();
        this.updateInterval = setInterval(() => {
            if (AppState.currentPage === 'dashboard') {
                this.updateMetrics();
                this.updateIncidents();
            }
        }, CONFIG.refreshInterval);
    },

    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
};

// ==================== Camera Module ====================
const Camera = {
    stream: null,
    placeholder: null,
    statusEl: null,
    toggleEl: null,
    toggleStatusTextEls: [],
    toggleStatusIndicatorEls: [],
    historyEl: null,
    historyClearBtn: null,
    manualEnabled: false,
    retryTimer: null,
    healthTimer: null,
    retryDelayMs: 2000,
    maxRetryDelayMs: 15000,

    init() {
        this.stream = document.getElementById('video-stream');
        this.placeholder = document.getElementById('camera-placeholder');
        this.statusEl = document.getElementById('stream-status');
        this.toggleEl = document.getElementById('camera-toggle');
        this.toggleStatusTextEls = Array.from(document.querySelectorAll('.camera-status-text'));
        this.toggleStatusIndicatorEls = Array.from(document.querySelectorAll('.camera-status-indicator'));
        this.historyEl = document.getElementById('camera-history');
        this.historyClearBtn = document.getElementById('camera-history-clear');

        if (!this.stream || !this.placeholder) return;

        if (this.toggleEl) {
            this.toggleEl.addEventListener('change', () => this.handleToggle());
        }

        if (this.historyClearBtn) {
            this.historyClearBtn.addEventListener('click', () => this.clearHistory());
        }

        this.updateToggleStatus(false);
        this.applyAccessControl();
        this.updateHistoryUI();
        this.updateSystemStatus(false);

        this.stream.onerror = () => this.handleStreamError('Stream disconnected');
        this.stream.onload = () => {
            this.stream.style.display = 'block';
            this.stream.style.visibility = 'visible';
            this.placeholder.style.display = 'none';
            AppState.cameraActive = true;
            this.retryDelayMs = 2000;
            this.updateToggleStatus(true);
            this.updateStatus('LIVE - Connected', '#10B981');
            this.startHealthCheck();
        };

        this.updateStatus('Camera Offline', '#EF4444');
    },

    async startStream() {
        if (!this.manualEnabled) {
            return;
        }
        try {
            // Check camera availability
            const status = await API.get('/api/video/status');
            Utils.log('Camera status:', status);

            if (!status.camera_enabled) {
                this.updateToggleStatus(false);
                this.updateSystemStatus(false);
                this.updateStatus('Camera Disabled', '#EF4444');
                return;
            }

            // Always attempt to start the stream (this triggers backend camera init)
            this.stream.src = `${CONFIG.cameraFeedUrl}?t=${Date.now()}`;

            if (status.streaming) {
                this.stream.style.display = 'block';
                this.stream.style.visibility = 'visible';
                this.placeholder.style.display = 'none';

                AppState.cameraActive = true;
                this.retryDelayMs = 2000;
                this.updateToggleStatus(true);
                this.updateSystemStatus(true);
                this.updateStatus('LIVE - Connected', '#10B981');
                this.startHealthCheck();
            } else {
                AppState.cameraActive = false;
                this.stream.style.display = 'block';
                this.stream.style.visibility = 'hidden';
                this.placeholder.style.display = 'flex';
                this.updateToggleStatus(false);
                this.updateSystemStatus(false);
                this.updateStatus('Camera Offline - Retrying...', '#F59E0B');
                this.scheduleRetry();
            }
        } catch (error) {
            Utils.error('Camera initialization error:', error);
            this.updateToggleStatus(false);
            this.updateSystemStatus(false);
            this.updateStatus('Connection Error - Retrying...', '#EF4444');
            this.scheduleRetry();
        }
    },

    isAdmin() {
        return AppState.userData && AppState.userData.role === 'admin';
    },

    applyAccessControl() {
        if (!this.toggleEl) return;
        const admin = this.isAdmin();
        this.toggleEl.disabled = !admin;
        if (!admin) {
            this.updateStatus('Restricted - Admin Only', '#EF4444');
        }
    },

    updateToggleStatus(isActive) {
        if (this.toggleEl) {
            this.toggleEl.checked = Boolean(isActive);
        }
        this.toggleStatusTextEls.forEach(el => {
            el.textContent = isActive ? 'ACTIVE' : 'OFFLINE';
        });
        this.toggleStatusIndicatorEls.forEach(el => {
            el.classList.toggle('active', Boolean(isActive));
        });
    },

    updateSystemStatus(isActive) {
        const systemStatusText = document.getElementById('system-status-text');
        const systemStatusIndicator = document.getElementById('system-status-indicator');
        if (!systemStatusText || !systemStatusIndicator) return;
        systemStatusText.textContent = isActive ? 'Connected / Active' : 'Offline';
        systemStatusIndicator.classList.toggle('active', Boolean(isActive));
    },

    async handleToggle() {
        if (!this.toggleEl) return;

        if (!this.isAdmin()) {
            this.toggleEl.checked = AppState.cameraActive;
            this.updateStatus('Access Restricted - Admin Only', '#EF4444');
            return;
        }

        const enable = this.toggleEl.checked;
        if (enable) {
            this.manualEnabled = true;
            await API.post('/api/camera/control', { enable: true });
            this.startStream();
        } else {
            this.manualEnabled = false;
            await API.post('/api/camera/control', { enable: false });
            AppState.cameraActive = false;
            this.stopHealthCheck();
            this.clearRetry();
            this.stream.style.display = 'block';
            this.stream.style.visibility = 'hidden';
            this.placeholder.style.display = 'flex';
            this.stream.src = '';
            this.updateToggleStatus(false);
            this.updateSystemStatus(false);
            this.updateStatus('Camera Disabled', '#EF4444');
        }

        this.logAccess(enable ? 'enable' : 'disable');
    },

    async logAccess(action) {
        this.appendHistory(action);
        try {
            await API.post('/api/audit/camera', {
                action,
                status: action === 'enable' ? 'ACTIVE' : 'OFFLINE',
                user: AppState.userData ? (AppState.userData.username || AppState.userData.name || 'unknown') : 'unknown'
            });
        } catch (error) {
            Utils.error('Camera audit log failed:', error);
        }
    },

    appendHistory(action) {
        const entry = {
            action,
            status: action === 'enable' ? 'ACTIVE' : 'OFFLINE',
            user: AppState.userData ? (AppState.userData.username || AppState.userData.name || 'unknown') : 'unknown',
            time: new Date().toISOString()
        };

        const history = this.getHistory();
        history.unshift(entry);
        localStorage.setItem('cameraAudit', JSON.stringify(history.slice(0, 20)));
        this.updateHistoryUI();
    },

    getHistory() {
        try {
            const raw = localStorage.getItem('cameraAudit');
            return raw ? JSON.parse(raw) : [];
        } catch (error) {
            return [];
        }
    },

    updateHistoryUI() {
        if (!this.historyEl) return;
        const history = this.getHistory();
        if (!history.length) {
            this.historyEl.innerHTML = '<li><i class="fas fa-circle"></i> No actions logged yet.</li>';
            return;
        }

        this.historyEl.innerHTML = history.map(entry => {
            const time = new Date(entry.time).toLocaleString('en-IN');
            return `<li><i class="fas fa-check-circle"></i> ${time} — ${entry.status} by ${entry.user}</li>`;
        }).join('');
    },

    clearHistory() {
        localStorage.removeItem('cameraAudit');
        this.updateHistoryUI();
    },

    handleStreamError(message) {
        Utils.error('Camera stream error:', message);
        if (!this.manualEnabled) {
            this.updateStatus('Camera Disabled', '#EF4444');
            return;
        }
        AppState.cameraActive = false;
        this.stream.style.display = 'block';
        this.stream.style.visibility = 'hidden';
        this.placeholder.style.display = 'flex';
        this.updateToggleStatus(false);
        this.updateSystemStatus(false);
        this.updateStatus('Stream Error - Reconnecting...', '#EF4444');
        this.scheduleRetry();
    },

    startHealthCheck() {
        if (this.healthTimer) return;
        this.healthTimer = setInterval(async () => {
            if (!AppState.cameraActive) return;
            try {
                const status = await API.get('/api/video/status');
                if (!status.streaming) {
                    this.handleStreamError('Camera unavailable');
                }
            } catch (error) {
                this.handleStreamError('Status check failed');
            }
        }, 5000);
    },

    stopHealthCheck() {
        if (this.healthTimer) {
            clearInterval(this.healthTimer);
            this.healthTimer = null;
        }
    },

    scheduleRetry() {
        if (!this.manualEnabled) return;
        if (this.retryTimer) return;
        this.stopHealthCheck();
        this.retryTimer = setTimeout(() => {
            this.retryTimer = null;
            this.startStream();
            this.retryDelayMs = Math.min(this.retryDelayMs * 2, this.maxRetryDelayMs);
        }, this.retryDelayMs);
    },

    clearRetry() {
        if (this.retryTimer) {
            clearTimeout(this.retryTimer);
            this.retryTimer = null;
        }
    },

    updateStatus(text, color) {
        if (this.statusEl) {
            this.statusEl.textContent = text;
            this.statusEl.style.color = color;
        }
    },

    toggle() {
        if (!this.stream || !this.placeholder) return;

        if (this.toggleEl) {
            this.toggleEl.click();
        }
    },

    async capture() {
        if (!AppState.cameraActive) return;

        try {
            await API.get('/api/video/status');
            this.updateStatus('Frame Captured!', '#10B981');
            setTimeout(() => this.updateStatus('LIVE - Connected', '#10B981'), 2000);
        } catch (error) {
            Utils.error('Frame capture error:', error);
        }
    }
};

// Global camera functions for button onclick handlers
window.toggleCamera = () => Camera.toggle();
window.captureFrame = () => Camera.capture();

// ==================== PPE Compliance Module ====================
const PPE = {
    async load() {
        Utils.log('Loading PPE compliance data...');
        await this.updateCompliance();
        await this.updateNonCompliant();
        await ViolationSnapshots.load();
        this.initFilters();
    },

    async updateCompliance() {
        try {
            const data = await API.get('/api/ppe-compliance');
            Utils.log('PPE data:', data);
            
            // Update progress bars if needed
            this.animateProgressBars();
        } catch (error) {
            Utils.error('Failed to update PPE compliance:', error);
        }
    },

    async updateNonCompliant() {
        try {
            const data = await API.get('/api/ppe-compliance');
            const tbody = document.getElementById('non-compliant-tbody');
            
            if (!tbody || !data.non_compliant) return;

            tbody.innerHTML = data.non_compliant.map(worker => `
                <tr>
                    <td>${worker.employee_id}</td>
                    <td>${worker.name}</td>
                    <td>${worker.missing_ppe}</td>
                    <td><span class="badge badge-${worker.alerts > 3 ? 'danger' : 'warning'}">${worker.alerts}</span></td>
                </tr>
            `).join('');
        } catch (error) {
            Utils.error('Failed to update non-compliant workers:', error);
        }
    },

    animateProgressBars() {
        document.querySelectorAll('.progress-fill').forEach(bar => {
            const width = bar.style.width;
            bar.style.width = '0';
            setTimeout(() => {
                bar.style.width = width;
            }, 100);
        });
    },

    initFilters() {
        const zoneFilter = document.getElementById('zone-filter');
        const dateFilter = document.getElementById('date-filter');

        if (zoneFilter) {
            zoneFilter.addEventListener('change', Utils.debounce(() => this.load(), 300));
        }

        if (dateFilter) {
            dateFilter.addEventListener('change', Utils.debounce(() => this.load(), 300));
        }
    }
};

// ==================== Violation Snapshots Module ====================
const ViolationSnapshots = {
    initialized: false,
    page: 1,
    lastCount: 0,
    currentViolationId: null,

    async load() {
        if (!this.initialized) {
            this.bindEvents();
            this.initialized = true;
        }
        await this.refreshGrid();
    },

    buildQuery(params) {
        const search = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                search.append(key, value);
            }
        });
        const query = search.toString();
        return query ? `?${query}` : '';
    },

    async fetchList(params) {
        return API.get(`/api/violations${this.buildQuery(params)}`);
    },

    async refreshGrid() {
        const zone = document.getElementById('zone-filter')?.value || '';
        const date = document.getElementById('date-filter')?.value || '';

        try {
            const data = await this.fetchList({
                limit: CONFIG.violationSnapshotLimit,
                zone,
                date
            });
            this.renderGrid(data.items || []);
            this.updateCountBadge(data.items || []);
        } catch (error) {
            Utils.error('Failed to load violation snapshots:', error);
        }
    },

    updateCountBadge(items) {
        const badge = document.getElementById('violation-snapshots-count');
        if (badge) {
            badge.textContent = items.length;
        }
    },

    renderGrid(items) {
        const grid = document.getElementById('violation-snapshots-grid');
        if (!grid) return;

        if (!items.length) {
            grid.innerHTML = '<div class="snapshot-empty">No recent violations captured.</div>';
            return;
        }

        grid.innerHTML = items.map(item => {
            const timestamp = Utils.formatDateTime(item.timestamp);
            const zone = item.zone || 'Unassigned';
            const camera = item.camera || '-';
            const missing = item.missing_ppe || 'Helmet';
            return `
                <button class="snapshot-card" data-violation-id="${item.id}" aria-label="View violation ${timestamp}">
                    <img src="${item.thumbnail_url}" alt="Violation snapshot">
                    <div class="snapshot-overlay">
                        <div class="snapshot-meta">${timestamp}</div>
                        <div class="snapshot-badges">
                            <span class="badge badge-info">${camera}</span>
                            <span class="badge badge-warning">${zone}</span>
                            <span class="badge badge-danger">${missing}</span>
                        </div>
                    </div>
                </button>
            `;
        }).join('');

        grid.querySelectorAll('[data-violation-id]').forEach(card => {
            card.addEventListener('click', () => this.openDetail(card.dataset.violationId));
        });
    },

    bindEvents() {
        const filterButton = document.getElementById('violation-snapshots-filter');
        const viewAllButton = document.getElementById('violation-snapshots-view-all');
        const drawer = document.getElementById('violation-drawer');
        const drawerClose = document.getElementById('violation-drawer-close');
        const applyFilters = document.getElementById('violation-filter-apply');
        const prevPage = document.getElementById('violation-prev-page');
        const nextPage = document.getElementById('violation-next-page');

        filterButton?.addEventListener('click', () => this.openDrawer());
        viewAllButton?.addEventListener('click', () => this.openDrawer());
        drawerClose?.addEventListener('click', () => this.closeDrawer());
        drawer?.addEventListener('click', (event) => {
            if (event.target === drawer) {
                this.closeDrawer();
            }
        });
        applyFilters?.addEventListener('click', () => {
            this.page = 1;
            this.refreshDrawer();
        });
        prevPage?.addEventListener('click', () => {
            if (this.page > 1) {
                this.page -= 1;
                this.refreshDrawer();
            }
        });
        nextPage?.addEventListener('click', () => {
            if (this.lastCount >= CONFIG.violationPageSize) {
                this.page += 1;
                this.refreshDrawer();
            }
        });

        const modal = document.getElementById('violation-modal');
        modal?.addEventListener('click', (event) => {
            if (event.target === modal) {
                this.closeModal();
            }
        });
        document.querySelectorAll('[data-modal-close]').forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                this.closeModal();
                this.closeDrawer();
            }
        });

        const zoneFilter = document.getElementById('zone-filter');
        const drawerZone = document.getElementById('violation-filter-zone');
        if (zoneFilter && drawerZone) {
            drawerZone.innerHTML = zoneFilter.innerHTML;
        }
    },

    openDrawer() {
        const drawer = document.getElementById('violation-drawer');
        if (!drawer) return;
        drawer.classList.add('active');
        drawer.setAttribute('aria-hidden', 'false');
        this.refreshDrawer();
    },

    closeDrawer() {
        const drawer = document.getElementById('violation-drawer');
        if (!drawer) return;
        drawer.classList.remove('active');
        drawer.setAttribute('aria-hidden', 'true');
    },

    async refreshDrawer() {
        const zone = document.getElementById('violation-filter-zone')?.value || '';
        const camera = document.getElementById('violation-filter-camera')?.value || '';
        const date = document.getElementById('violation-filter-date')?.value || '';
        const status = document.getElementById('violation-filter-status')?.value || '';

        try {
            const data = await this.fetchList({
                limit: CONFIG.violationPageSize,
                offset: (this.page - 1) * CONFIG.violationPageSize,
                zone,
                camera,
                date,
                status
            });
            this.lastCount = (data.items || []).length;
            this.renderDrawerList(data.items || []);
            this.updateDrawerPagination();
        } catch (error) {
            Utils.error('Failed to load violation list:', error);
        }
    },

    renderDrawerList(items) {
        const list = document.getElementById('violation-drawer-list');
        if (!list) return;
        if (!items.length) {
            list.innerHTML = '<div class="snapshot-empty">No violations found for the selected filters.</div>';
            return;
        }

        list.innerHTML = items.map(item => {
            const timestamp = Utils.formatDateTime(item.timestamp);
            const zone = item.zone || 'Unassigned';
            const camera = item.camera || '-';
            const status = item.status || 'new';
            return `
                <button class="snapshot-row" data-violation-id="${item.id}" aria-label="Open violation ${timestamp}">
                    <img src="${item.thumbnail_url}" alt="Violation thumbnail">
                    <div>
                        <div><strong>${timestamp}</strong></div>
                        <div>${camera} • ${zone}</div>
                        <div>Status: ${status}</div>
                    </div>
                </button>
            `;
        }).join('');

        list.querySelectorAll('[data-violation-id]').forEach(row => {
            row.addEventListener('click', () => this.openDetail(row.dataset.violationId));
        });
    },

    updateDrawerPagination() {
        const indicator = document.getElementById('violation-page-indicator');
        const prevBtn = document.getElementById('violation-prev-page');
        const nextBtn = document.getElementById('violation-next-page');
        if (indicator) indicator.textContent = `Page ${this.page}`;
        if (prevBtn) prevBtn.disabled = this.page <= 1;
        if (nextBtn) nextBtn.disabled = this.lastCount < CONFIG.violationPageSize;
    },

    async openDetail(violationId) {
        if (!violationId) return;
        this.currentViolationId = violationId;
        try {
            const data = await API.get(`/api/violations/${encodeURIComponent(violationId)}`);
            this.renderDetail(data);
            this.showModal();
        } catch (error) {
            Utils.error('Failed to load violation detail:', error);
        }
    },

    renderDetail(data) {
        const image = document.getElementById('violation-modal-image');
        const timestamp = document.getElementById('violation-modal-timestamp');
        const meta = document.getElementById('violation-modal-meta');
        const download = document.getElementById('violation-download');
        const markReviewed = document.getElementById('violation-mark-reviewed');
        const timeline = document.getElementById('violation-timeline');

        if (image) image.src = data.image_url || '';
        if (timestamp) timestamp.textContent = `${Utils.formatDateTime(data.timestamp)} • ${data.camera_id || '-'}`;
        if (download) download.href = data.image_url || '#';
        if (timeline) {
            const query = new URLSearchParams({
                camera: data.camera_id || '',
                timestamp: data.timestamp || ''
            });
            timeline.href = `/timeline?${query.toString()}`;
        }

        if (meta) {
            const bbox = Array.isArray(data.bbox) ? data.bbox.join(', ') : '-';
            meta.innerHTML = `
                <div><strong>Camera:</strong> ${data.camera_id || '-'}</div>
                <div><strong>Zone:</strong> ${data.zone || 'Unassigned'}</div>
                <div><strong>Missing PPE:</strong> ${data.missing_ppe || 'Helmet'}</div>
                <div><strong>Status:</strong> ${data.status || 'new'}</div>
                <div><strong>Confidence:</strong> ${data.confidence ?? '-'}</div>
                <div><strong>Helmet Conf:</strong> ${data.helmet_confidence ?? '-'}</div>
                <div><strong>Frame #:</strong> ${data.frame_number ?? '-'}</div>
                <div><strong>Model:</strong> ${data.model || '-'}</div>
                <div><strong>BBox:</strong> ${bbox}</div>
            `;
        }

        if (markReviewed) {
            markReviewed.onclick = () => this.markReviewed();
        }
    },

    showModal() {
        const modal = document.getElementById('violation-modal');
        if (!modal) return;
        modal.classList.add('active');
        modal.setAttribute('aria-hidden', 'false');
    },

    closeModal() {
        const modal = document.getElementById('violation-modal');
        if (!modal) return;
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');
    },

    async markReviewed() {
        if (!this.currentViolationId) return;
        try {
            await API.post(`/api/violations/${encodeURIComponent(this.currentViolationId)}/review`, {});
            await this.refreshGrid();
            await this.refreshDrawer();
            this.closeModal();
        } catch (error) {
            Utils.error('Failed to mark violation reviewed:', error);
        }
    }
};

// ==================== Attendance Module ====================
const Attendance = {
    async load() {
        Utils.log('Loading attendance data...');
        const today = new Date().toISOString().split('T')[0];
        
        const dateInput = document.getElementById('attendance-date');
        if (dateInput) {
            dateInput.value = today;
        }

        await this.updateAttendance(today);
        this.initFilters();
    },

    async updateAttendance(date) {
        try {
            const data = await API.get(`/api/attendance?date=${date}`);
            
            const presentCount = document.getElementById('present-count');
            const absentCount = document.getElementById('absent-count');

            if (presentCount) presentCount.textContent = data.present || 234;
            if (absentCount) absentCount.textContent = data.absent || 13;

            await this.updateAttendanceTable(data.records);
        } catch (error) {
            Utils.error('Failed to update attendance:', error);
        }
    },

    async updateAttendanceTable(records) {
        const tbody = document.getElementById('attendance-tbody');
        if (!tbody || !records) return;

        tbody.innerHTML = records.map(record => `
            <tr>
                <td>${record.employee_id}</td>
                <td>${record.name}</td>
                <td>${record.department || '-'}</td>
                <td>${record.check_in || '-'}</td>
                <td>${record.check_out || '-'}</td>
                <td><span class="badge badge-${this.getStatusBadge(record.status)}">${record.status}</span></td>
            </tr>
        `).join('');
    },

    getStatusBadge(status) {
        const badges = {
            'Present': 'success',
            'Absent': 'danger',
            'In Progress': 'info',
            'Late': 'warning'
        };
        return badges[status] || 'info';
    },

    initFilters() {
        const dateInput = document.getElementById('attendance-date');
        const deptFilter = document.getElementById('department-filter');

        if (dateInput) {
            dateInput.addEventListener('change', (e) => {
                this.updateAttendance(e.target.value);
            });
        }

        if (deptFilter) {
            deptFilter.addEventListener('change', Utils.debounce(() => {
                const date = dateInput?.value || new Date().toISOString().split('T')[0];
                this.updateAttendance(date);
            }, 300));
        }
    }
};

// ==================== Form Validation Module ====================
const FormHandler = {
    init() {
        const contactForm = document.getElementById('contact-form');
        if (contactForm) {
            contactForm.addEventListener('submit', (e) => this.handleContactForm(e));
        }
    },

    async handleContactForm(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        // Validate
        if (!this.validateEmail(data.email)) {
            alert('Please enter a valid email address.');
            return;
        }

        if (!data.name || !data.message) {
            alert('Please fill in all required fields.');
            return;
        }

        try {
            // Simulate form submission
            Utils.log('Submitting contact form:', data);
            alert('Thank you for your message! We will get back to you soon.');
            e.target.reset();
        } catch (error) {
            Utils.error('Form submission error:', error);
            alert('An error occurred. Please try again later.');
        }
    },

    validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
};

// ==================== WebSocket Module (Optional) ====================
const WebSocketManager = {
    ws: null,
    reconnectInterval: null,

    init() {
        if (!CONFIG.enableWebSocket) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                Utils.log('WebSocket connected');
                this.stopReconnect();
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };

            this.ws.onerror = (error) => {
                Utils.error('WebSocket error:', error);
            };

            this.ws.onclose = () => {
                Utils.log('WebSocket disconnected');
                this.startReconnect();
            };
        } catch (error) {
            Utils.error('WebSocket initialization error:', error);
        }
    },

    handleMessage(data) {
        switch(data.type) {
            case 'fire_alert':
                this.showAlert('Critical', 'Fire Detected', data.location);
                Dashboard.updateMetrics();
                break;
            case 'ppe_violation':
                PPE.updateCompliance();
                ViolationSnapshots.refreshGrid();
                break;
            case 'attendance_update':
                Attendance.load();
                break;
        }
    },

    showAlert(type, title, message) {
        Utils.log(`Alert [${type}]: ${title} - ${message}`);
        // Implement custom alert UI here
    },

    startReconnect() {
        this.reconnectInterval = setInterval(() => this.init(), 3000);
    },

    stopReconnect() {
        if (this.reconnectInterval) {
            clearInterval(this.reconnectInterval);
            this.reconnectInterval = null;
        }
    }
};

// ==================== Application Initialization ====================
class IOCLApp {
    async init() {
        Utils.log('Initializing IOCL Refinery Safety System...');

        // Check authentication
        const isAuth = await Auth.checkAuth();
        
        if (isAuth) {
            // Initialize modules
            Navigation.init();
            FormHandler.init();

            // Check for hash in URL
            const hash = window.location.hash.slice(1);
            const initialPage = hash || 'home';
            Navigation.navigateTo(initialPage);

            // Optional: Initialize WebSocket
            // WebSocketManager.init();

            Utils.log('Application initialized successfully');
        }
    }

    destroy() {
        Dashboard.stopAutoUpdate();
        if (WebSocketManager.ws) {
            WebSocketManager.ws.close();
        }
    }
}

// ==================== Start Application ====================
const app = new IOCLApp();

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => app.init());
} else {
    app.init();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => app.destroy());

// Export for testing/debugging
if (CONFIG.enableDebug) {
    window.IOCLApp = {
        app,
        Auth,
        Navigation,
        Dashboard,
        Camera,
        PPE,
        ViolationSnapshots,
        Attendance,
        API,
        Utils
    };
}

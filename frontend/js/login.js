"use strict";

const form = document.getElementById('loginForm');
const msgEl = document.getElementById('login-message');
const spinner = document.getElementById('login-spinner');
const passwordInput = document.getElementById('password');

// Optional security hardening
document.addEventListener('contextmenu', (e) => e.preventDefault());
['copy', 'cut', 'paste'].forEach((evt) =>
    passwordInput?.addEventListener(evt, (e) => e.preventDefault())
);

const showMessage = (text, type = 'info') => {
    if (!msgEl) return;
    msgEl.textContent = text;
    msgEl.style.color = type === 'error'
        ? '#ff6961'
        : (type === 'success' ? '#7dffb0' : '#b7c0d6');
};

form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    spinner.style.display = 'inline-block';
    showMessage('Authenticating… Please wait.');

    const payload = {
        employeeId: document.getElementById('employeeId')?.value.trim(),
        password: passwordInput?.value || '',
        role: document.getElementById('role')?.value || ''
    };

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            showMessage(data.message || 'Invalid Credentials – Contact System Administrator', 'error');
            return;
        }

        if (data.user) {
            sessionStorage.setItem('iocl_user', JSON.stringify(data.user));
        }

        showMessage('Authentication Successful – Redirecting to Refinery Dashboard', 'success');
        setTimeout(() => window.location.href = '/', 800);
    } catch (err) {
        console.error('[Auth Error]', err);
        showMessage('Unauthorized Access Attempt Detected', 'error');
    } finally {
        spinner.style.display = 'none';
    }
});

// Verify session on load
window.addEventListener('load', async () => {
    try {
        const response = await fetch('/api/auth/verify', { credentials: 'include' });
        if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
                window.location.href = '/';
            }
        }
    } catch (err) {
        console.debug('Session verify failed on load:', err);
    }
});

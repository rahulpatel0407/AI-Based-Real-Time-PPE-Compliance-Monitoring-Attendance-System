'use strict';

const toggle = document.getElementById('profile-toggle');
const dropdown = document.getElementById('profile-dropdown');
const upload = document.getElementById('avatar-upload');
const preview = document.getElementById('profile-preview');
const avatarImg = document.getElementById('profile-avatar-img');

const nameEl = document.getElementById('profile-name');
const roleEl = document.getElementById('profile-role');
const empEl = document.getElementById('profile-empid');
const deptEl = document.getElementById('profile-dept');
const lastLoginEl = document.getElementById('profile-lastlogin');
const navName = document.getElementById('navbar-username');

const setProfileData = (user) => {
    if (!user) return;
    nameEl.textContent = user.name || 'Authorized User';
    roleEl.textContent = user.role || 'Role';
    empEl.textContent = user.employeeId || 'EMP0000';
    deptEl.textContent = user.department || 'Operations';
    lastLoginEl.textContent = user.lastLogin || new Date().toLocaleString('en-IN');
    navName.textContent = user.name || 'Authorized User';
    if (user.avatarUrl) {
        preview.src = user.avatarUrl;
        avatarImg.src = user.avatarUrl;
    }
};

const hydrateFromSession = () => {
    const cached = JSON.parse(sessionStorage.getItem('iocl_user') || 'null');
    if (cached) setProfileData(cached);
};

const loadProfile = async () => {
    try {
        const res = await fetch('/api/profile', { credentials: 'include' });
        if (!res.ok) {
            window.location.href = '/login';
            return;
        }
        const data = await res.json();
        if (data && data.user) {
            sessionStorage.setItem('iocl_user', JSON.stringify(data.user));
            setProfileData(data.user);
        }
    } catch (err) {
        console.error('[Profile] load failed', err);
    }
};

hydrateFromSession();
loadProfile();

if (toggle && dropdown) {
    toggle.addEventListener('click', () => {
        const isHidden = dropdown.getAttribute('aria-hidden') === 'true';
        dropdown.setAttribute('aria-hidden', String(!isHidden));
    });

    document.addEventListener('click', (e) => {
        if (!toggle.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.setAttribute('aria-hidden', 'true');
        }
    });
}

const MAX_SIZE = 2 * 1024 * 1024;
if (upload) {
    upload.addEventListener('change', () => {
        const file = upload.files[0];
        if (!file) return;

        if (!['image/jpeg', 'image/png'].includes(file.type) || file.size > MAX_SIZE) {
            alert('Invalid image. Only JPG/PNG up to 2MB allowed.');
            upload.value = '';
            return;
        }

        const img = new Image();
        img.onload = () => {
            const size = 256;
            const canvas = document.createElement('canvas');
            canvas.width = size;
            canvas.height = size;

            const ctx = canvas.getContext('2d');
            const minSide = Math.min(img.width, img.height);
            const sx = (img.width - minSide) / 2;
            const sy = (img.height - minSide) / 2;
            ctx.drawImage(img, sx, sy, minSide, minSide, 0, 0, size, size);

            const dataUrl = canvas.toDataURL('image/png');
            preview.src = dataUrl;
            avatarImg.src = dataUrl;
        };
        img.src = URL.createObjectURL(file);
    });
}

const saveBtn = document.getElementById('save-avatar');
if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
        const file = upload?.files[0];
        if (!file) return alert('Select an image first.');

        const formData = new FormData();
        formData.append('avatar', file);

        try {
            const res = await fetch('/api/profile/avatar', { method: 'POST', body: formData, credentials: 'include' });
            if (!res.ok) {
                alert('Upload failed. Contact system administrator.');
                return;
            }
            const data = await res.json();
            if (data.avatarUrl) {
                preview.src = data.avatarUrl;
                avatarImg.src = data.avatarUrl;
                const stored = JSON.parse(sessionStorage.getItem('iocl_user') || '{}');
                stored.avatarUrl = data.avatarUrl;
                sessionStorage.setItem('iocl_user', JSON.stringify(stored));
            }
            alert('Profile picture updated successfully.');
            upload.value = '';
        } catch (err) {
            console.error('[Profile] upload failed', err);
            alert('Upload failed. Contact system administrator.');
        }
    });
}

const logoutBtn = document.getElementById('logout-btn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
        try {
            await fetch('/api/logout', { method: 'POST', credentials: 'include' });
        } catch (err) {
            console.error('[Profile] logout failed', err);
        } finally {
            sessionStorage.clear();
            window.location.href = '/login';
        }
    });
}

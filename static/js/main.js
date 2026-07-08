// ===== THEME MANAGEMENT =====
function getTheme() {
  return localStorage.getItem('theme') || document.documentElement.getAttribute('data-theme') || 'dark';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  const icon = document.getElementById('themeIcon');
  if (icon) {
    icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
  }
}

function toggleTheme() {
  const current = getTheme();
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

// Sync theme icon on load (theme itself is applied by the inline <head> script)
(function() {
  const icon = document.getElementById('themeIcon');
  if (icon) {
    icon.className = getTheme() === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
  }
})();

// ===== SIDEBAR MANAGEMENT =====
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar) {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
  }
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar) {
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
  }
}

// ===== INLINE NOTIFICATIONS =====
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('inlineNotifications');
  if (!container) return;

  const id = 'notif-' + Date.now();
  const iconMap = {
    success: 'fas fa-check-circle',
    error: 'fas fa-times-circle',
    warning: 'fas fa-exclamation-triangle',
    info: 'fas fa-info-circle'
  };
  const alertType = type === 'error' ? 'danger' : type;

  const el = document.createElement('div');
  el.id = id;
  el.className = `alert alert-${alertType} alert-dismissible fade show d-flex align-items-center gap-2 mb-2`;
  el.setAttribute('role', 'alert');
  el.innerHTML = `
    <i class="${iconMap[type] || iconMap.info} flex-shrink-0"></i>
    <span class="flex-grow-1">${message}</span>
    <button type="button" class="btn-close" onclick="this.closest('.alert').remove()"></button>
  `;
  container.prepend(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  if (duration > 0) {
    setTimeout(() => {
      if (document.getElementById(id)) {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 300);
      }
    }, duration);
  }
}

// ===== INLINE CONFIRM =====
function _escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showConfirm(message, onConfirm) {
  if (typeof onConfirm !== 'function') return;
  let container = document.getElementById('inlineNotifications');
  if (!container) {
    // Create a floating container so we never fall back to window.confirm()
    container = document.createElement('div');
    container.id = 'inlineNotifications';
    container.style.cssText = [
      'position:fixed', 'top:70px', 'left:50%', 'transform:translateX(-50%)',
      'width:90%', 'max-width:640px', 'z-index:10500', 'pointer-events:auto'
    ].join(';');
    document.body.appendChild(container);
  }

  // Remove any existing confirm prompt
  container.querySelectorAll('.inline-confirm').forEach(el => el.remove());

  const id = 'confirm-' + Date.now();
  const el = document.createElement('div');
  el.id = id;
  el.className = 'alert alert-warning inline-confirm d-flex align-items-center gap-3 mb-2';
  el.setAttribute('role', 'alert');
  el.innerHTML = `
    <i class="fas fa-exclamation-triangle flex-shrink-0"></i>
    <span class="flex-grow-1">${_escHtml(message)}</span>
    <button class="btn btn-sm btn-danger" id="${id}-ok">Yes, continue</button>
    <button class="btn btn-sm btn-outline-secondary" id="${id}-no">Cancel</button>
  `;
  container.prepend(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  document.getElementById(`${id}-ok`).onclick = function() {
    el.remove();
    onConfirm();
  };
  document.getElementById(`${id}-no`).onclick = function() {
    el.remove();
  };
}

// ===== CSRF PROTECTION =====
// Automatically inject the CSRF token into all same-origin POST/PUT/DELETE fetch calls
// and into all HTML forms on DOMContentLoaded.
(function() {
  const getMeta = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  // Intercept fetch so every mutating request carries the CSRF token header
  const _fetch = window.fetch;
  window.fetch = function(url, opts = {}) {
    const method = (opts.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      const token = getMeta();
      if (token) {
        opts.headers = opts.headers || {};
        if (opts.headers instanceof Headers) {
          if (!opts.headers.has('X-CSRFToken')) opts.headers.set('X-CSRFToken', token);
        } else {
          opts.headers['X-CSRFToken'] = opts.headers['X-CSRFToken'] || token;
        }
      }
    }
    return _fetch.apply(this, [url, opts]);
  };

  // Inject hidden csrf_token field into every HTML form that submits via POST
  document.addEventListener('DOMContentLoaded', function() {
    const token = getMeta();
    if (!token) return;
    document.querySelectorAll('form').forEach(function(form) {
      const method = (form.method || 'get').toLowerCase();
      if (method === 'post' && !form.querySelector('[name="csrf_token"]')) {
        const inp = document.createElement('input');
        inp.type = 'hidden';
        inp.name = 'csrf_token';
        inp.value = token;
        form.appendChild(inp);
      }
    });
  });
})();

// ===== GENERAL AJAX FETCH HELPER =====
async function apiPost(url, data = {}) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return resp.json();
}

// ===== TITLES PREVIEW ENDPOINT (for new project form) =====
// Register a route in Flask for /api/generate-titles-preview
// (handled by the main blueprint - see routes/main.py extension below)

// ===== NAVBAR SCROLL EFFECT =====
window.addEventListener('scroll', function() {
  const topnav = document.querySelector('.topnav');
  if (topnav) {
    topnav.style.boxShadow = window.scrollY > 10 ? '0 2px 16px rgba(0,0,0,0.3)' : '';
  }
});

// ===== AUTO-DISMISS ALERTS =====
setTimeout(() => {
  document.querySelectorAll('.alert.alert-success').forEach(el => {
    if (el.querySelector('.btn-close')) {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 300);
    }
  });
}, 5000);


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

// Apply theme on load
(function() {
  const saved = localStorage.getItem('theme');
  if (saved) applyTheme(saved);
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

// ===== TOAST NOTIFICATIONS =====
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const id = 'toast-' + Date.now();
  const iconMap = {
    success: 'fas fa-check-circle text-success',
    error: 'fas fa-times-circle text-danger',
    warning: 'fas fa-exclamation-triangle text-warning',
    info: 'fas fa-info-circle text-info'
  };

  const toastEl = document.createElement('div');
  toastEl.id = id;
  toastEl.className = 'toast align-items-center show';
  toastEl.setAttribute('role', 'alert');
  toastEl.innerHTML = `
    <div class="d-flex align-items-center">
      <div class="toast-body d-flex align-items-center gap-2">
        <i class="${iconMap[type] || iconMap.info}"></i>
        <span>${message}</span>
      </div>
      <button type="button" class="btn-close me-2 ms-auto" onclick="this.closest('.toast').remove()"></button>
    </div>
  `;
  container.appendChild(toastEl);
  setTimeout(() => { if (document.getElementById(id)) toastEl.remove(); }, duration);
}

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

// ===== BOOTSTRAP TOOLTIPS =====
document.addEventListener('DOMContentLoaded', function() {
  const tooltipEls = document.querySelectorAll('[title]');
  tooltipEls.forEach(el => {
    if (!el.dataset.bsToggle) {
      new bootstrap.Tooltip(el, { trigger: 'hover', placement: 'top' });
    }
  });
});

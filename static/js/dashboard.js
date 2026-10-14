/**
 * Core Dashboard JavaScript.
 * Manages UTC clock, auto-refresh polling intervals, toast notifications,
 * and global pipeline execution triggers.
 */

let refreshTimer = null;
let currentRefreshInterval = 5; // seconds

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  startUtcClock();
  setupRefreshTimer();
});

// Update UTC clock every second
function startUtcClock() {
  const clockEl = document.getElementById('utcClock');
  if (!clockEl) return;

  function tick() {
    const now = new Date();
    clockEl.textContent = now.toUTCString().replace('GMT', 'UTC');
  }
  tick();
  setInterval(tick, 1000);
}

// Configurable Auto-Refresh Polling
function updateRefreshInterval(seconds) {
  currentRefreshInterval = parseInt(seconds, 10);
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
  setupRefreshTimer();
  showToast(`Auto-refresh set to ${currentRefreshInterval === 0 ? 'Off' : currentRefreshInterval + 's'}`, 'info');
}

function setupRefreshTimer() {
  if (currentRefreshInterval > 0) {
    refreshTimer = setInterval(() => {
      if (typeof onAutoRefresh === 'function') {
        onAutoRefresh();
      }
    }, currentRefreshInterval * 1000);
  }
}

// Global Pipeline Trigger Action (from sidebar button)
async function triggerIngestionCycle() {
  const btn = document.getElementById('btnSidebarTrigger');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Ingesting...';
  }

  try {
    const res = await fetch('/api/pipeline/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ batch_size: 200 })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Batch completed: ${data.data.records_processed} valid, ${data.data.records_rejected} quarantined.`, 'success');
      if (typeof onAutoRefresh === 'function') {
        onAutoRefresh();
      }
    } else {
      showToast(`Ingestion failed: ${data.message}`, 'error');
    }
  } catch (err) {
    showToast(`Network error: ${err}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '▶ Run Ingestion Cycle';
    }
  }
}

// Lightweight Toast Notification System
function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toastContainer';
    toastContainer.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      pointer-events: none;
    `;
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const bgColors = {
    success: '#065f46',
    error: '#991b1b',
    info: '#1e293b',
    warning: '#92400e'
  };
  const borderColors = {
    success: '#10b981',
    error: '#ef4444',
    info: '#3b82f6',
    warning: '#f59e0b'
  };

  toast.style.cssText = `
    background-color: ${bgColors[type] || bgColors.info};
    border: 1px solid ${borderColors[type] || borderColors.info};
    color: #f8fafc;
    padding: 12px 18px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.25s ease;
    pointer-events: auto;
  `;
  toast.textContent = message;

  toastContainer.appendChild(toast);

  // Animate in
  setTimeout(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  }, 10);

  // Remove after 3.5 seconds
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

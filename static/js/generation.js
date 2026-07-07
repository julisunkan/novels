// ===== GENERATION PAGE CONTROLLER =====
let pollInterval = null;
let isRunning = false;

function initGeneration(projectId, initialStatus, totalChapters) {
  if (initialStatus === 'generating') {
    startPolling(projectId);
    updateButtonStates('generating');
  } else if (initialStatus === 'pausing') {
    startPolling(projectId);
    updateButtonStates('pausing');
  } else {
    updateButtonStates(initialStatus);
  }
}

async function startGeneration() {
  const projectId = getProjectId();
  setStatusText('Starting generation…', 'fas fa-spinner fa-spin');
  try {
    const data = await apiPost(`/project/${projectId}/generate/start`);
    if (data.error) {
      showToast(data.error, 'error');
      updateButtonStates('draft');
      return;
    }
    showToast('Generation started!', 'success');
    updateButtonStates('generating');
    startPolling(projectId);
  } catch(e) {
    showToast('Failed to start: ' + e.message, 'error');
  }
}

async function pauseGeneration() {
  const projectId = getProjectId();
  const data = await apiPost(`/project/${projectId}/generate/pause`);
  if (data.success) {
    showToast('Generation pausing after current chapter…', 'warning');
    updateButtonStates('pausing');
    setStatusText('Pausing…', 'fas fa-pause-circle');
  }
}

async function resumeGeneration() {
  const projectId = getProjectId();
  setStatusText('Resuming…', 'fas fa-spinner fa-spin');
  try {
    const data = await apiPost(`/project/${projectId}/generate/resume`);
    if (data.error) { showToast(data.error, 'error'); return; }
    showToast('Generation resumed!', 'success');
    updateButtonStates('generating');
    startPolling(projectId);
  } catch(e) {
    showToast('Failed to resume: ' + e.message, 'error');
  }
}

// Override start button to handle resume
document.addEventListener('DOMContentLoaded', function() {
  const startBtn = document.getElementById('btnStart');
  if (startBtn) {
    startBtn.addEventListener('click', function() {
      const status = this.dataset.status || window.PROJECT_STATUS_CURRENT || 'draft';
      if (status === 'paused') {
        resumeGeneration();
      } else {
        startGeneration();
      }
    });
  }
});

async function stopGeneration() {
  if (!confirm('Stop generation? You can resume later from where you left off.')) return;
  const projectId = getProjectId();
  const data = await apiPost(`/project/${projectId}/generate/stop`);
  if (data.success) {
    showToast('Generation stopped. You can resume later.', 'warning');
    stopPolling();
    updateButtonStates('paused');
    setStatusText('Stopped', 'fas fa-pause-circle');
  }
}

function startPolling(projectId) {
  stopPolling();
  isRunning = true;
  pollInterval = setInterval(() => fetchProgress(projectId), 2500);
  fetchProgress(projectId);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
  isRunning = false;
}

async function fetchProgress(projectId) {
  try {
    const resp = await fetch(`/api/project/${projectId}/progress`);
    const data = await resp.json();
    if (data.error) return;
    updateProgressUI(data);

    // Stop polling if done or paused and thread not alive
    if (data.status === 'completed') {
      stopPolling();
      updateButtonStates('completed');
      setStatusText('Completed!', 'fas fa-check-circle');
      showToast('Book generation complete!', 'success');
    } else if ((data.status === 'paused' || data.status === 'draft') && !data.thread_alive) {
      stopPolling();
      updateButtonStates(data.status);
      setStatusText('Paused', 'fas fa-pause-circle');
    } else if (data.status === 'generating' || data.thread_alive) {
      updateButtonStates('generating');
    }
  } catch(e) {
    console.warn('Progress fetch failed:', e);
  }
}

function updateProgressUI(data) {
  // Progress bar
  const bar = document.getElementById('mainProgressBar');
  if (bar) {
    bar.style.width = data.progress_pct + '%';
    bar.setAttribute('aria-valuenow', data.progress_pct);
  }

  const pct = document.getElementById('progressPct');
  if (pct) pct.textContent = data.progress_pct + '%';

  // Stats
  setText('statChapters', `${data.generated_chapters} / ${data.total_chapters}`);
  setText('statWords', data.total_words.toLocaleString());
  if (data.last_tokens) setText('statTokens', data.last_tokens.toLocaleString());
  if (data.last_gen_time) setText('statTime', data.last_gen_time + 's');
  setText('wordsGenerated', data.total_words.toLocaleString());

  // Current task
  if (data.current_chapter) {
    const taskEl = document.getElementById('currentTaskText');
    if (taskEl) taskEl.textContent = `Writing Chapter ${data.current_chapter}: ${data.current_chapter_title || ''}`;
  }

  // Update chapter status grid
  if (data.chapters) {
    data.chapters.forEach(ch => {
      const el = document.getElementById(`ch-${ch.chapter_number}`);
      if (!el) return;
      el.className = el.className.replace(/status-\w+/, '') + ` status-${ch.status}`;
      const cpStatus = el.querySelector('.cp-status');
      if (cpStatus) {
        if (ch.status === 'generated') {
          cpStatus.innerHTML = `<span class="text-success"><i class="fas fa-check"></i> ${ch.word_count.toLocaleString()} words</span>`;
          const cpNum = el.querySelector('.cp-num');
          if (cpNum) cpNum.style.background = 'rgba(16,185,129,0.2)';
        } else if (ch.status === 'generating') {
          cpStatus.innerHTML = `<span class="text-primary"><i class="fas fa-spinner fa-spin"></i> Generating…</span>`;
        }
      }
    });
  }
}

function updateButtonStates(status) {
  const btnStart = document.getElementById('btnStart');
  const btnPause = document.getElementById('btnPause');
  const btnStop  = document.getElementById('btnStop');

  if (!btnStart) return;

  const setDisabled = (btn, val) => { if (btn) btn.disabled = val; };

  // Enable/disable per-chapter generate buttons based on bulk state
  const isBulkActive = (status === 'generating' || status === 'pausing');
  document.querySelectorAll('.btn-generate-chapter').forEach(b => { b.disabled = isBulkActive; });

  if (status === 'generating') {
    setDisabled(btnStart, true);
    setDisabled(btnPause, false);
    setDisabled(btnStop, false);
    btnStart.innerHTML = '<i class="fas fa-play me-2"></i>Generating…';
  } else if (status === 'pausing') {
    setDisabled(btnStart, true);
    setDisabled(btnPause, true);
    setDisabled(btnStop, false);
    btnStart.innerHTML = '<i class="fas fa-play me-2"></i>Pausing…';
  } else if (status === 'paused') {
    setDisabled(btnStart, false);
    setDisabled(btnPause, true);
    setDisabled(btnStop, true);
    btnStart.innerHTML = '<i class="fas fa-play me-2"></i>Resume';
    btnStart.dataset.status = 'paused';
  } else if (status === 'completed') {
    setDisabled(btnStart, false);
    setDisabled(btnPause, true);
    setDisabled(btnStop, true);
    btnStart.innerHTML = '<i class="fas fa-redo me-2"></i>Regenerate';
  } else {
    setDisabled(btnStart, false);
    setDisabled(btnPause, true);
    setDisabled(btnStop, true);
    btnStart.innerHTML = '<i class="fas fa-play me-2"></i>Start Generation';
  }
}

async function generateSingleChapter(chapterNumber) {
  const projectId = getProjectId();
  const el = document.getElementById(`ch-${chapterNumber}`);
  const btn = el ? el.querySelector('.btn-generate-chapter') : null;
  const label = el ? el.querySelector('.chapter-pending-label') : null;

  // Optimistic UI: show spinner immediately
  if (el) {
    el.className = el.className.replace(/status-\w+/, '') + ' status-generating';
  }
  if (btn) btn.disabled = true;
  if (label) label.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating…';

  try {
    const resp = await fetch(`/project/${projectId}/generate/chapter/${chapterNumber}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await resp.json();

    if (data.error) {
      showToast(data.error, 'error');
      // Revert to pending
      if (el) el.className = el.className.replace(/status-\w+/, '') + ' status-pending';
      if (label) label.innerHTML = '<i class="fas fa-clock"></i> Pending';
      if (btn) btn.disabled = false;
      return;
    }

    // Success: update to generated state
    if (el) {
      el.className = el.className.replace(/status-\w+/, '') + ' status-generated';
      const cpStatus = el.querySelector('.cp-status');
      if (cpStatus) {
        cpStatus.innerHTML = `<span class="text-success"><i class="fas fa-check"></i> ${data.word_count.toLocaleString()} words</span>`;
      }
      const cpNum = el.querySelector('.cp-num');
      if (cpNum) cpNum.style.background = 'rgba(16,185,129,0.2)';
    }
    showToast(`Chapter ${chapterNumber} generated!`, 'success');

    // Refresh overall progress stats
    fetchProgress(projectId);
  } catch (e) {
    showToast('Generation failed: ' + e.message, 'error');
    if (el) el.className = el.className.replace(/status-\w+/, '') + ' status-pending';
    if (label) label.innerHTML = '<i class="fas fa-clock"></i> Pending';
    if (btn) btn.disabled = false;
  }
}

function setStatusText(text, iconClass) {
  const el = document.getElementById('statusText');
  if (el) el.innerHTML = `<i class="${iconClass} me-2"></i>${text}`;
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function getProjectId() {
  return typeof PROJECT_ID !== 'undefined' ? PROJECT_ID : 0;
}

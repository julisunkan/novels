// ===== MANUSCRIPT EDITOR =====
// Relies on CHAPTERS_DATA, PROJECT_ID, TARGET_WORDS, ACTIVE_CHAPTER_ID
// injected by editor.html.

// ── State ──────────────────────────────────────────────────────────────────
let currentChapterId = null;   // ID of the chapter currently shown
let currentChapterIdx = -1;    // Index into CHAPTERS_DATA
let isDirty = false;           // Unsaved changes flag
let isLoading = false;         // Fetch in progress flag
let autosaveTimer = null;
let wcRafId = null;            // requestAnimationFrame handle for word count

// Client-side content cache: Map<chapterId, string>
// Avoids re-fetching chapters the user has already visited.
const chapterCache = new Map();

// ── DOM references (resolved once) ─────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  restoreFormatPrefs();

  // Determine which chapter to open first
  const firstId = ACTIVE_CHAPTER_ID && CHAPTERS_DATA.some(c => c.id === ACTIVE_CHAPTER_ID)
    ? ACTIVE_CHAPTER_ID
    : (CHAPTERS_DATA[0]?.id ?? null);

  if (firstId) loadChapter(firstId);
});

// Warn if the user tries to leave with unsaved changes
window.addEventListener('beforeunload', function (e) {
  if (isDirty) {
    e.preventDefault();
    e.returnValue = '';
  }
});

// ── Load chapter ──────────────────────────────────────────────────────────
async function loadChapter(id) {
  if (isLoading) return;
  if (id === currentChapterId && !isDirty) return; // already showing this chapter clean

  // Auto-save before switching — only clear dirty after confirmed success
  if (isDirty && currentChapterId) {
    const savingId = currentChapterId;
    const saved = await saveCurrentChapter(true, savingId);
    if (!saved) {
      // Save failed; abort switch so the user doesn't lose edits
      showToast('Could not save current chapter. Please try again before switching.', 'error');
      return;
    }
    isDirty = false;
  }

  const idx = CHAPTERS_DATA.findIndex(c => c.id === id);
  if (idx === -1) return;

  currentChapterId = id;
  currentChapterIdx = idx;
  const ch = CHAPTERS_DATA[idx];

  // Update sidebar active state
  document.querySelectorAll('.editor-chapter-btn').forEach(b => b.classList.remove('active'));
  $(`chbtn-${id}`)?.classList.add('active');
  $(`chbtn-${id}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

  // Update toolbar title
  if ($('editorChapterTitle')) $('editorChapterTitle').textContent = `Ch ${ch.num}: ${ch.title}`;

  // Update prev/next nav buttons
  updateNavButtons(idx);

  // Enable Save button
  const saveBtn = $('saveBtn');
  if (saveBtn) saveBtn.disabled = false;

  const textarea = $('editorArea');
  if (!textarea) return;

  // If content is cached, render immediately (no spinner)
  if (chapterCache.has(id)) {
    textarea.value = chapterCache.get(id);
    textarea.disabled = false;
    scheduleWordCount();
    setAutosaveIndicator('saved', 'All changes saved');
    isDirty = false;
    return;
  }

  // Show loading overlay
  showOverlay(true);
  textarea.disabled = true;
  setAutosaveIndicator('', 'Loading…');

  isLoading = true;
  try {
    const resp = await fetch(`/project/${PROJECT_ID}/editor/chapter/${id}/content`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    const content = data.content || '';
    chapterCache.set(id, content);
    textarea.value = content;
    textarea.disabled = false;
    textarea.focus();
    scheduleWordCount();
    setAutosaveIndicator('saved', 'All changes saved');
    isDirty = false;
  } catch (e) {
    setAutosaveIndicator('error', 'Failed to load chapter');
    showToast('Could not load chapter: ' + e.message, 'error');
    // Restore textarea so the user isn't stranded
    textarea.disabled = false;
  } finally {
    isLoading = false;
    showOverlay(false);
  }
}

// ── Input handler ─────────────────────────────────────────────────────────
function onEditorInput() {
  isDirty = true;
  setAutosaveIndicator('dirty', 'Unsaved changes…');

  // Update cache immediately so navigating away uses latest text
  if (currentChapterId !== null) {
    chapterCache.set(currentChapterId, $('editorArea').value);
  }

  // Throttle word count via rAF
  scheduleWordCount();

  // Debounced autosave (3 s of inactivity)
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => {
    if (isDirty) saveCurrentChapter(true);
  }, 3000);
}

// ── Word count (rAF-throttled) ────────────────────────────────────────────
function scheduleWordCount() {
  if (wcRafId) return;
  wcRafId = requestAnimationFrame(() => {
    wcRafId = null;
    const text = $('editorArea')?.value || '';
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    const chars = text.length;
    const wc = $('editorWordCount');
    const cc = $('editorCharCount');
    if (wc) wc.textContent = words.toLocaleString() + ' words';
    if (cc) cc.textContent = chars.toLocaleString() + ' chars';
  });
}

// ── Save ──────────────────────────────────────────────────────────────────
// Returns true on success, false on failure.
async function saveCurrentChapter(silent = false, chapterId = null) {
  const targetId = chapterId ?? currentChapterId;
  if (!targetId) return true; // nothing to save

  const textarea = $('editorArea');
  if (!textarea) return true;

  const content = textarea.value;

  setSaveBtn('saving');
  if (!silent) setAutosaveIndicator('dirty', 'Saving…');

  try {
    const resp = await fetch(`/project/${PROJECT_ID}/editor/chapter/${targetId}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    });
    const data = await resp.json();

    if (data.success) {
      // Only clear dirty flag if the chapter on screen is the one we just saved
      if (targetId === currentChapterId) {
        isDirty = false;
        const ts = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        setAutosaveIndicator('saved', `Saved at ${ts}`);
      }
      // Update sidebar word count
      const wc = $(`wc-${targetId}`);
      if (wc) wc.textContent = data.word_count.toLocaleString() + ' words';
      // Update CHAPTERS_DATA in memory
      const ci = CHAPTERS_DATA.findIndex(c => c.id === targetId);
      if (ci !== -1) CHAPTERS_DATA[ci].words = data.word_count;

      refreshTotalWordCount();
      setSaveBtn('idle');
      if (!silent) showToast('Chapter saved!', 'success');
      return true;
    } else {
      setSaveBtn('idle');
      const msg = data.error || 'Save failed';
      setAutosaveIndicator('error', msg);
      if (!silent) showToast('Save failed: ' + msg, 'error');
      return false;
    }
  } catch (e) {
    setSaveBtn('idle');
    setAutosaveIndicator('error', 'Save failed');
    if (!silent) showToast('Save failed: ' + e.message, 'error');
    return false;
  }
}

// ── Navigation ────────────────────────────────────────────────────────────
function navigateChapter(delta) {
  const newIdx = currentChapterIdx + delta;
  if (newIdx < 0 || newIdx >= CHAPTERS_DATA.length) return;
  loadChapter(CHAPTERS_DATA[newIdx].id);
}

function updateNavButtons(idx) {
  const prev = $('btnPrevChapter');
  const next = $('btnNextChapter');
  if (prev) prev.disabled = idx <= 0;
  if (next) next.disabled = idx >= CHAPTERS_DATA.length - 1;
}

// ── Filter sidebar ────────────────────────────────────────────────────────
function filterChapters(query) {
  const q = query.trim().toLowerCase();
  document.querySelectorAll('.editor-chapter-btn').forEach(btn => {
    const match = !q || btn.dataset.search.includes(q);
    btn.classList.toggle('ec-hidden', !match);
  });
}

// ── Format preferences ────────────────────────────────────────────────────
const PREFS_KEY = 'editorPrefs';

function restoreFormatPrefs() {
  try {
    const prefs = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
    if (prefs.font) { $('fontFamily').value = prefs.font; applyFont(false); }
    if (prefs.size) { $('fontSize').value = prefs.size; applyFontSize(false); }
    if (prefs.lh)   { $('lineHeight').value = prefs.lh; applyLineHeight(false); }
    if (prefs.align) setAlign(prefs.align, false);
  } catch (_) {}
}

function saveFormatPrefs() {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify({
      font:  $('fontFamily')?.value,
      size:  $('fontSize')?.value,
      lh:    $('lineHeight')?.value,
      align: $('editorArea')?.style.textAlign || 'left'
    }));
  } catch (_) {}
}

function applyFont(persist = true) {
  const font = $('fontFamily')?.value;
  const ta = $('editorArea');
  if (font && ta) ta.style.fontFamily = font;
  if (persist) saveFormatPrefs();
}

function applyFontSize(persist = true) {
  const size = $('fontSize')?.value;
  const ta = $('editorArea');
  if (size && ta) ta.style.fontSize = size + 'px';
  if (persist) saveFormatPrefs();
}

function applyLineHeight(persist = true) {
  const lh = $('lineHeight')?.value;
  const ta = $('editorArea');
  if (lh && ta) ta.style.lineHeight = lh;
  if (persist) saveFormatPrefs();
}

function setAlign(align, persist = true) {
  const ta = $('editorArea');
  if (ta) ta.style.textAlign = align;
  if (persist) saveFormatPrefs();
}

// ── Total word count ──────────────────────────────────────────────────────
function refreshTotalWordCount() {
  const total = CHAPTERS_DATA.reduce((sum, c) => sum + (c.words || 0), 0);
  const el = $('totalWordCount');
  if (el) el.textContent = total.toLocaleString();

  const fill = $('progressFill');
  if (fill && TARGET_WORDS > 0) {
    fill.style.width = Math.min(total / TARGET_WORDS * 100, 100).toFixed(1) + '%';
  }
}

// ── Search & Replace ─────────────────────────────────────────────────────
async function doReplace(replaceAll) {
  const find       = $('findInput')?.value;
  const replace    = $('replaceInput')?.value ?? '';
  const matchCase  = $('matchCase')?.checked;
  const wholeWord  = $('wholeWord')?.checked;
  const resultEl   = $('replaceResult');

  if (!find) { showToast('Enter a search term', 'warning'); return; }

  // Flush any unsaved local edits before the server rewrites chapter content
  if (isDirty && currentChapterId) {
    const saved = await saveCurrentChapter(true);
    if (!saved) {
      showToast('Could not save current chapter before replacing. Please try again.', 'error');
      return;
    }
    isDirty = false;
  }

  try {
    const resp = await fetch(`/project/${PROJECT_ID}/search-replace`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ find, replace, match_case: matchCase, whole_word: wholeWord, replace_all: replaceAll })
    });
    const data = await resp.json();

    if (data.success) {
      const msg = data.replaced > 0
        ? `Replaced ${data.replaced} occurrence(s) across all chapters.`
        : 'No matches found.';
      if (resultEl) resultEl.textContent = msg;
      if (data.replaced > 0) {
        showToast(msg, 'success');
        // Invalidate cache for every chapter (content changed server-side)
        chapterCache.clear();
        // Reload currently visible chapter
        if (currentChapterId) {
          const id = currentChapterId;
          currentChapterId = null; // force reload
          loadChapter(id);
        }
      }
    } else {
      const err = data.error || 'Replace failed';
      if (resultEl) resultEl.textContent = err;
      showToast(err, 'error');
    }
  } catch (e) {
    showToast('Replace failed: ' + e.message, 'error');
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────
function showOverlay(visible) {
  $('editorLoadOverlay')?.classList.toggle('visible', visible);
}

function setAutosaveIndicator(state, text) {
  const el = $('autosaveIndicator');
  if (!el) return;
  el.textContent = text;
  el.className = 'autosave-indicator';
  if (state === 'dirty') el.classList.add('autosave-dirty');
  if (state === 'error') el.classList.add('autosave-error');
  // 'saved' keeps the default green class from CSS
}

function setSaveBtn(state) {
  const icon  = $('saveBtnIcon');
  const label = $('saveBtnLabel');
  if (!icon || !label) return;
  if (state === 'saving') {
    icon.className = 'fas fa-spinner fa-spin me-1';
    label.textContent = 'Saving…';
  } else {
    icon.className = 'fas fa-save me-1';
    label.textContent = 'Save';
  }
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────
document.addEventListener('keydown', function (e) {
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 's') {
      e.preventDefault();
      saveCurrentChapter();
    } else if (e.key === '[') {
      e.preventDefault();
      navigateChapter(-1);
    } else if (e.key === ']') {
      e.preventDefault();
      navigateChapter(1);
    } else if (e.key === 'f') {
      e.preventDefault();
      new bootstrap.Modal($('searchModal')).show();
    }
  }
});

// ===== MANUSCRIPT EDITOR =====
let currentChapterId = null;
let autosaveTimer = null;
let isDirty = false;

document.addEventListener('DOMContentLoaded', function() {
  const textarea = document.getElementById('editorArea');
  const chapterId = document.getElementById('currentChapterId');

  if (textarea && chapterId && chapterId.value) {
    currentChapterId = chapterId.value;
    updateCounts(textarea.value);
  }
});

function loadChapter(id, num, title, content) {
  // Autosave current chapter before switching
  if (isDirty && currentChapterId) {
    saveCurrentChapter(true);
  }

  currentChapterId = id;
  const textarea = document.getElementById('editorArea');
  const titleEl = document.getElementById('editorChapterTitle');
  const hiddenId = document.getElementById('currentChapterId');

  if (textarea) {
    textarea.value = content;
    updateCounts(content);
  }
  if (titleEl) titleEl.textContent = `Chapter ${num}: ${title}`;
  if (hiddenId) hiddenId.value = id;

  // Update active state in sidebar
  document.querySelectorAll('.editor-chapter-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`chbtn-${id}`)?.classList.add('active');

  isDirty = false;
  setAutosaveIndicator('All changes saved');
}

function onEditorInput() {
  isDirty = true;
  const textarea = document.getElementById('editorArea');
  if (textarea) updateCounts(textarea.value);
  setAutosaveIndicator('Unsaved changes…');

  // Debounced autosave
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => {
    if (isDirty) saveCurrentChapter(true);
  }, 3000);
}

function updateCounts(text) {
  const words = text ? text.match(/\b\w+\b/g)?.length || 0 : 0;
  const chars = text ? text.length : 0;
  const wcEl = document.getElementById('editorWordCount');
  const ccEl = document.getElementById('editorCharCount');
  if (wcEl) wcEl.textContent = words.toLocaleString() + ' words';
  if (ccEl) ccEl.textContent = chars.toLocaleString() + ' chars';
}

async function saveCurrentChapter(silent = false) {
  if (!currentChapterId) return;
  const textarea = document.getElementById('editorArea');
  const projectId = document.getElementById('currentProjectId')?.value;
  if (!textarea || !projectId) return;

  const content = textarea.value;
  try {
    const resp = await fetch(`/project/${projectId}/editor/chapter/${currentChapterId}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    });
    const data = await resp.json();
    if (data.success) {
      isDirty = false;
      setAutosaveIndicator('All changes saved');
      // Update word count in sidebar
      const chBtn = document.getElementById(`chbtn-${currentChapterId}`);
      if (chBtn) {
        const wcEl = chBtn.querySelector('.ec-words');
        if (wcEl) wcEl.textContent = data.word_count.toLocaleString() + ' words';
      }
      // Update total
      updateTotalWordCount(projectId);
      if (!silent) showToast('Chapter saved!', 'success');
    }
  } catch(e) {
    if (!silent) showToast('Save failed: ' + e.message, 'error');
  }
}

async function updateTotalWordCount(projectId) {
  // Recalculate from all chapter buttons
  let total = 0;
  document.querySelectorAll('.editor-chapter-btn .ec-words').forEach(el => {
    total += parseInt(el.textContent.replace(/\D/g, '')) || 0;
  });
  const el = document.querySelector('.editor-wordcount span');
  if (el) el.textContent = total.toLocaleString();
}

function setAutosaveIndicator(text) {
  const el = document.getElementById('autosaveIndicator');
  if (el) el.textContent = text;
}

// ===== FORMATTING =====
function applyFont() {
  const font = document.getElementById('fontFamily')?.value;
  const textarea = document.getElementById('editorArea');
  if (font && textarea) textarea.style.fontFamily = font;
}

function applyFontSize() {
  const size = document.getElementById('fontSize')?.value;
  const textarea = document.getElementById('editorArea');
  if (size && textarea) textarea.style.fontSize = size + 'px';
}

function applyLineHeight() {
  const lh = document.getElementById('lineHeight')?.value;
  const textarea = document.getElementById('editorArea');
  if (lh && textarea) textarea.style.lineHeight = lh;
}

// ===== SEARCH & REPLACE =====
async function doReplace(replaceAll) {
  const find = document.getElementById('findInput')?.value;
  const replace = document.getElementById('replaceInput')?.value;
  const matchCase = document.getElementById('matchCase')?.checked;
  const wholeWord = document.getElementById('wholeWord')?.checked;
  const projectId = document.getElementById('currentProjectId')?.value;

  if (!find) { showToast('Enter a search term', 'warning'); return; }
  if (!projectId) return;

  try {
    const resp = await fetch(`/project/${projectId}/search-replace`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ find, replace, match_case: matchCase, whole_word: wholeWord, replace_all: replaceAll })
    });
    const data = await resp.json();
    const resultEl = document.getElementById('replaceResult');
    if (data.success) {
      const msg = data.replaced > 0
        ? `Replaced ${data.replaced} occurrence(s).`
        : 'No matches found.';
      if (resultEl) resultEl.textContent = msg;
      if (data.replaced > 0) {
        showToast(msg, 'success');
        // Reload current chapter content
        reloadCurrentChapter(projectId);
      }
    } else if (data.error) {
      if (resultEl) resultEl.textContent = data.error;
      showToast(data.error, 'error');
    }
  } catch(e) {
    showToast('Replace failed: ' + e.message, 'error');
  }
}

async function reloadCurrentChapter(projectId) {
  if (!currentChapterId) return;
  // The chapter content was changed server-side; reload to reflect
  // For now, just indicate stale state
  setAutosaveIndicator('Content updated server-side. Reload to see changes.');
}

// ===== KEYBOARD SHORTCUTS =====
document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault();
    saveCurrentChapter();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault();
    const modal = new bootstrap.Modal(document.getElementById('searchModal'));
    modal.show();
  }
});

/* Notara — main application logic */

// ── State ───────────────────────────────────────────────────
let selectedFile = null;
let ytReady = false;
let currentJobId = null;
let pollTimer = null;
let resultsData = null;
let activeTab = 'guitar1';
const toggleState = { multi: false, bass: false, vocal: false, drums: false, keys: false };
let pwaInstallPrompt = null;
let selectedLyricsFile = null;

// ── DOM refs ─────────────────────────────────────────────────
const ytInput       = document.getElementById('yt-input');
const btnFetch      = document.getElementById('btn-fetch');
const dropZone      = document.getElementById('drop-zone');
const fileInput     = document.getElementById('file-input');
const btnBrowse     = document.getElementById('btn-browse');
const fileIndicator = document.getElementById('file-indicator');
const btnTranscribe = document.getElementById('btn-transcribe');
const stateEmpty    = document.getElementById('state-empty');
const stateProgress = document.getElementById('state-progress');
const stateError    = document.getElementById('state-error');
const stateResults  = document.getElementById('state-results');
const progressSteps = document.getElementById('progress-steps');
const tabSwitcher   = document.getElementById('tab-switcher');
const tabContent    = document.getElementById('tab-content');
const tabDownloads  = document.getElementById('tab-downloads');
const panelRight    = document.getElementById('panel-right');
const btnPwaInstall = document.getElementById('btn-pwa-install');

const lyricsToggle    = document.getElementById('lyrics-toggle');
const lyricsBody      = document.getElementById('lyrics-body');
const lyricsDrop      = document.getElementById('lyrics-drop');
const lyricsFileInput = document.getElementById('lyrics-file-input');
const lyricsBrowse    = document.getElementById('lyrics-browse');
const lyricsIndicator = document.getElementById('lyrics-file-indicator');
const lyricsTextarea  = document.getElementById('lyrics-textarea');

// ── PWA Install ──────────────────────────────────────────────
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  pwaInstallPrompt = e;
  btnPwaInstall.style.display = 'block';
});
btnPwaInstall.addEventListener('click', async () => {
  if (!pwaInstallPrompt) return;
  pwaInstallPrompt.prompt();
  const { outcome } = await pwaInstallPrompt.userChoice;
  if (outcome === 'accepted') btnPwaInstall.style.display = 'none';
  pwaInstallPrompt = null;
});
window.addEventListener('appinstalled', () => {
  btnPwaInstall.style.display = 'none';
  pwaInstallPrompt = null;
});

// ── YouTube ──────────────────────────────────────────────────
ytInput.addEventListener('input', () => {
  ytReady = ytInput.value.trim().length > 0;
  btnFetch.disabled = !ytReady;
  _updateTranscribeButton();
});

btnFetch.addEventListener('click', () => {
  selectedFile = null;
  fileIndicator.style.display = 'none';
  _updateTranscribeButton();
});

// ── File drop ────────────────────────────────────────────────
btnBrowse.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) _setFile(fileInput.files[0]);
});

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) _setFile(e.dataTransfer.files[0]);
});

dropZone.addEventListener('click', e => {
  if (e.target !== btnBrowse) fileInput.click();
});

function _setFile(file) {
  selectedFile = file;
  ytInput.value = '';
  ytReady = false;
  btnFetch.disabled = true;
  fileIndicator.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
  fileIndicator.style.display = 'block';
  _updateTranscribeButton();
}

// ── Toggles ──────────────────────────────────────────────────
function _setupToggle(id, key) {
  const container = document.getElementById(`toggle-${id}`);
  container.querySelectorAll('[data-val]').forEach(btn => {
    btn.addEventListener('click', () => {
      const val = btn.dataset.val === '1';
      toggleState[key] = val;
      container.querySelectorAll('[data-val]').forEach(b => {
        b.className = b.dataset.val === '1' && val || b.dataset.val === '0' && !val
          ? 'toggle-yes' : 'toggle-no';
      });
    });
  });
}
_setupToggle('multi', 'multi');
_setupToggle('bass', 'bass');
_setupToggle('vocal', 'vocal');
_setupToggle('drums', 'drums');
_setupToggle('keys', 'keys');

// Hide tuning hint when user picks a non-default (non-auto) tuning
document.getElementById('opt-tuning')?.addEventListener('change', e => {
  const hint = document.getElementById('tuning-hint');
  if (hint) hint.style.display = e.target.value === 'auto' ? '' : 'none';
});

// Hide key hint when user picks a specific key
document.getElementById('opt-key')?.addEventListener('change', e => {
  const hint = document.getElementById('key-hint');
  if (hint) hint.style.display = e.target.value === 'auto' ? '' : 'none';
});

// ── Lyrics section ────────────────────────────────────────────
lyricsToggle.addEventListener('click', () => {
  const open = lyricsBody.style.display !== 'none';
  lyricsBody.style.display = open ? 'none' : 'flex';
  lyricsToggle.textContent = '';
  lyricsToggle.appendChild(document.createTextNode(open ? '+ ADD LYRICS ' : '− REMOVE LYRICS '));
  const hint = document.createElement('span');
  hint.className = 'lyrics-toggle-hint';
  hint.textContent = 'optional';
  lyricsToggle.appendChild(hint);
});

lyricsBrowse.addEventListener('click', () => lyricsFileInput.click());

lyricsFileInput.addEventListener('change', () => {
  if (lyricsFileInput.files[0]) _setLyricsFile(lyricsFileInput.files[0]);
});

lyricsDrop.addEventListener('dragover', e => { e.preventDefault(); lyricsDrop.classList.add('drag-over'); });
lyricsDrop.addEventListener('dragleave', () => lyricsDrop.classList.remove('drag-over'));
lyricsDrop.addEventListener('drop', e => {
  e.preventDefault();
  lyricsDrop.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) _setLyricsFile(e.dataTransfer.files[0]);
});

function _setLyricsFile(file) {
  selectedLyricsFile = file;
  lyricsIndicator.textContent = `Selected: ${file.name}`;
  lyricsIndicator.style.display = 'block';
  lyricsTextarea.value = '';
}

// ── Transcribe button ────────────────────────────────────────
function _updateTranscribeButton() {
  btnTranscribe.disabled = !selectedFile && !ytReady;
}

btnTranscribe.addEventListener('click', _submitJob);

// ── Job submission ───────────────────────────────────────────
async function _submitJob() {
  btnTranscribe.disabled = true;
  currentJobId = null;
  resultsData = null;

  _showState('progress');

  const formData = new FormData();
  if (selectedFile) {
    formData.append('file', selectedFile);
  } else {
    formData.append('youtube_url', ytInput.value.trim());
  }
  formData.append('tuning', document.getElementById('opt-tuning').value);
  formData.append('key', document.getElementById('opt-key').value);
  formData.append('multi_guitar', toggleState.multi);
  formData.append('bass_tab', toggleState.bass);
  formData.append('vocal_tab', toggleState.vocal);
  formData.append('drum_summary', toggleState.drums);
  formData.append('keys_tab', toggleState.keys);
  if (selectedLyricsFile) {
    formData.append('lyrics_file', selectedLyricsFile);
  } else if (lyricsTextarea.value.trim()) {
    formData.append('lyrics_text', lyricsTextarea.value.trim());
  }
  // Reset after reading so a subsequent job starts clean
  selectedLyricsFile = null;

  try {
    const resp = await fetch(`${API_BASE_URL}/api/jobs`, { method: 'POST', body: formData });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    currentJobId = data.job_id;
    _startPolling();
  } catch (err) {
    _showError(`Failed to start job: ${err.message}`);
    btnTranscribe.disabled = false;
  }
}

// ── Progress polling ─────────────────────────────────────────
function _startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(_poll, 3000);
  _poll();
}

async function _poll() {
  if (!currentJobId) return;
  try {
    const resp = await fetch(`${API_BASE_URL}/api/jobs/${currentJobId}/status`);
    const data = await resp.json();

    _updateProgress(data);

    if (data.status === 'done') {
      clearInterval(pollTimer);
      await _loadResults();
    } else if (data.status === 'error') {
      clearInterval(pollTimer);
      _showError(`Processing failed: ${data.error || 'Unknown error'}`);
      btnTranscribe.disabled = false;
    }
  } catch (err) {
    // Network hiccup — keep polling
  }
}

function _updateProgress(data) {
  const total = data.total_steps || 6;
  progressSteps.innerHTML = '';
  for (let i = 1; i <= total; i++) {
    const div = document.createElement('div');
    div.className = 'progress-step';
    const dot = document.createElement('div');
    dot.className = 'step-dot' + (i < data.step ? ' done' : i === data.step ? ' active' : '');
    const label = document.createElement('span');
    label.className = 'step-label' + (i > data.step ? ' pending' : '');
    label.textContent = i === data.step ? data.step_label : (i < data.step ? data.step_label : '...');
    div.appendChild(dot);
    div.appendChild(label);
    progressSteps.appendChild(div);
  }
  // Show current step label at the active dot
  if (data.step_label) {
    const steps = progressSteps.querySelectorAll('.step-label');
    if (steps[data.step - 1]) steps[data.step - 1].textContent = data.step_label;
  }
}

// ── Results ──────────────────────────────────────────────────
async function _loadResults() {
  try {
    const resp = await fetch(`${API_BASE_URL}/api/jobs/${currentJobId}/results`);
    resultsData = await resp.json();
    _renderResults(resultsData);
    // Load audio
    const audio = document.getElementById('audio-player');
    audio.src = `${API_BASE_URL}/api/jobs/${currentJobId}/audio`;
    // Init playback
    if (window.initPlayback) window.initPlayback(audio, resultsData.bars);
    _showState('results');
    // Reveal right panel on mobile
    panelRight.classList.remove('hidden');
    // Re-enable so user can run another job without re-selecting files
    btnTranscribe.disabled = false;
  } catch (err) {
    _showError(`Failed to load results: ${err.message}`);
    btnTranscribe.disabled = false;
  }
}

function _renderResults(data) {
  // Build tab switcher
  tabSwitcher.innerHTML = '';
  const tabs = Object.keys(data.tabs);
  tabs.forEach((t, i) => {
    const btn = document.createElement('div');
    btn.className = 'tab-btn' + (i === 0 ? ' active' : '');
    btn.textContent = _tabLabel(t);
    btn.dataset.track = t;
    btn.addEventListener('click', () => _switchTab(t, tabs));
    tabSwitcher.appendChild(btn);
  });
  activeTab = tabs[0];
  _renderTab(activeTab, data);
}

function _tabLabel(track) {
  return { guitar1: 'Guitar 1', guitar2: 'Guitar 2', bass: 'Bass', vocals: 'Vocals', drums: 'Drums', keys: 'Keys', lyrics: 'Lyrics' }[track] || track;
}

function _isChordAnnotationLine(line) {
  const s = line.trim();
  return s.length > 0 && !/[a-z]/.test(s);
}

function _switchTab(track, allTracks) {
  activeTab = track;
  tabSwitcher.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.track === track);
  });
  _renderTab(track, resultsData);
}

function _renderTab(track, data) {
  const text = data.tabs[track] || '';
  tabContent.innerHTML = '';

  if (track === 'keys') {
    tabContent.innerHTML = '';
    const box = document.createElement('div');
    box.className = 'keys-summary';
    // Parse the first line for the note count
    const firstLine = text.split('\n')[0] || text;
    box.innerHTML = `
      <div class="keys-icon">♩</div>
      <div class="keys-message">${firstLine}</div>
      <div class="keys-sub">Download MIDI to open in GarageBand, Ableton, or any DAW.</div>
    `;
    tabContent.appendChild(box);
    // Still show download buttons (already handled below in the function)
    tabDownloads.innerHTML = '';
    tabDownloads.appendChild(_dlBtn('↓ MIDI', 'dl-midi', 'keys', 'midi'));
    tabDownloads.appendChild(_dlBtn('↓ TXT', 'dl-txt', 'keys', 'txt'));
    return;
  }

  if (track === 'lyrics') {
    tabContent.innerHTML = '';
    const lines = text.split('\n');
    lines.forEach(line => {
      const span = document.createElement('span');
      const stripped = line.trim();
      if (stripped.startsWith('[') && stripped.endsWith(']') && stripped.length > 2) {
        span.className = 'tab-comment';
      } else if (_isChordAnnotationLine(line)) {
        span.className = 'tab-chord-line';
        span.dataset.origChordLine = line;
      } else {
        span.className = 'tab-lyric-line';
      }
      span.textContent = line;
      tabContent.appendChild(span);
      tabContent.appendChild(document.createTextNode('\n'));
    });
    tabDownloads.innerHTML = '';
    tabDownloads.appendChild(_dlBtn('↓ TXT', 'dl-txt', 'lyrics', 'txt'));
    tabDownloads.appendChild(_dlBtn('↓ PDF', 'dl-pdf', 'lyrics', 'pdf'));
    return;
  }

  const segments = text.split('\n\n');
  segments.forEach(segment => {
    if (!segment.trim()) return;
    const isComment = segment.trim().split('\n').every(l => l.startsWith('#') || l.trim() === '');
    if (isComment) {
      segment.split('\n').forEach(line => {
        if (!line.trim()) return;
        const span = document.createElement('span');
        span.className = 'tab-comment';
        span.textContent = line;
        tabContent.appendChild(span);
        tabContent.appendChild(document.createTextNode('\n'));
      });
    } else {
      const span = document.createElement('span');
      span.className = 'tab-bar';
      span.textContent = segment;
      span.dataset.orig = segment;
      tabContent.appendChild(span);
      tabContent.appendChild(document.createTextNode('\n\n'));
    }
  });

  // Downloads
  tabDownloads.innerHTML = '';
  if (track !== 'drums') {
    const pdf = _dlBtn('↓ PDF', 'dl-pdf', track, 'pdf');
    const txt = _dlBtn('↓ TXT', 'dl-txt', track, 'txt');
    tabDownloads.appendChild(pdf);
    tabDownloads.appendChild(txt);
    if (['guitar1', 'guitar2', 'vocals', 'keys'].includes(track)) {
      tabDownloads.appendChild(_dlBtn('↓ MIDI', 'dl-midi', track, 'midi'));
    }
  } else {
    tabDownloads.appendChild(_dlBtn('↓ TXT', 'dl-txt', track, 'txt'));
  }
}

function _dlBtn(label, cls, track, fmt) {
  const btn = document.createElement('button');
  btn.className = cls;
  btn.textContent = label;
  btn.addEventListener('click', () => {
    window.open(`${API_BASE_URL}/api/jobs/${currentJobId}/download/${track}/${fmt}`);
  });
  return btn;
}

// ── UI state helpers ─────────────────────────────────────────
function _showState(state) {
  stateEmpty.style.display    = state === 'empty'    ? 'flex'  : 'none';
  stateProgress.style.display = state === 'progress' ? 'block' : 'none';
  stateError.style.display    = state === 'error'    ? 'block' : 'none';
  stateResults.style.display  = state === 'results'  ? 'flex'  : 'none';
}

function _showError(msg) {
  stateError.textContent = msg;
  _showState('error');
}

// Expose for playback.js
window.getActiveTab = () => activeTab;
window.getTabBars = () => resultsData ? resultsData.bars : [];

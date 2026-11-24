/* Notara — playback, chord trinity, timeline */

let _audio = null;
let _bars = [];
let _sections = [];
let _rafId = null;

const _SEC_DISPLAY = { intro: 'INTRO', verse: 'COUPLET', chorus: 'REFRAIN', bridge: 'PONT', outro: 'OUTRO' };

function _buildSectionTimeline() {
  const wrap = document.getElementById('section-timeline-wrap');
  const container = document.getElementById('section-timeline');
  if (!container || !_sections.length || !_audio || !_audio.duration) return;
  while (container.firstChild) container.removeChild(container.firstChild);
  const dur = _audio.duration;
  _sections.forEach(s => {
    const btn = document.createElement('button');
    btn.className = `section-pill section-pill-${s.type}`;
    btn.style.flexBasis = `${((s.end_sec - s.start_sec) / dur) * 100}%`;
    btn.textContent = _SEC_DISPLAY[s.type] || s.type.toUpperCase();
    btn.title = `${_SEC_DISPLAY[s.type] || s.type} — mesure ${s.bar_start + 1}`;
    btn.addEventListener('click', () => { if (_audio) { _audio.currentTime = s.start_sec; _updateTime(); _syncTab(); } });
    container.appendChild(btn);
  });
  if (wrap) wrap.style.display = 'block';
}
let _initialized = false;
let _tabBarCache = null;
let _transposeSteps = 0;
let _speed = 1.0;
let _lastActiveIdx = -2;  // -2 = force first update

const playBtn     = document.getElementById('play-btn');
const playIcon    = document.getElementById('play-icon');
const scrubber    = document.getElementById('scrubber');
const scrubFill   = document.getElementById('scrubber-fill');
const timeDisplay = document.getElementById('time-display');

// Trinity elements
const elBefore = document.getElementById('chord-before');
const elNow    = document.getElementById('chord-now');
const elNext   = document.getElementById('chord-next');
const elAfter  = document.getElementById('chord-after');
const diagBefore = document.getElementById('diag-before');
const diagNow    = document.getElementById('diag-now');
const diagNext   = document.getElementById('diag-next');
const diagAfter  = document.getElementById('diag-after');
const timeline   = document.getElementById('chord-timeline');

// ── Transpose helpers ────────────────────────────────────────
const _NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
const _ENHARMONIC = {Db:'C#',Eb:'D#',Gb:'F#',Ab:'G#',Bb:'A#'};

function _transposeChordName(name, steps) {
  if (!name || name === '—') return name;
  const m = name.match(/^([A-G][b#]?)(.*)$/);
  if (!m) return name;
  const root = _ENHARMONIC[m[1]] || m[1];
  const idx = _NOTES.indexOf(root);
  if (idx === -1) return name;
  return _NOTES[((idx + steps) % 12 + 12) % 12] + m[2];
}

function _shiftTabText(text, steps) {
  if (steps === 0) return text;
  return text.split('\n').map(line => {
    if (/^[A-Ga-g][#b]?\|/.test(line)) {
      return line.replace(/\d+/g, n => Math.max(0, parseInt(n) + steps).toString());
    }
    if (/^[A-G]/.test(line.trim()) && !line.trim().startsWith('#')) {
      return _transposeChordName(line.trim(), steps);
    }
    return line;
  }).join('\n');
}

// ── Timeline build ───────────────────────────────────────────
function _buildTimeline() {
  if (!timeline) return;
  timeline.innerHTML = '';
  _bars.forEach((bar, i) => {
    const pill = document.createElement('button');
    pill.className = 'chord-pill';
    pill.textContent = _transposeChordName(bar.label || 'N.C.', _transposeSteps);
    pill.dataset.idx = i;
    pill.addEventListener('click', () => {
      if (_audio) _audio.currentTime = bar.start_sec;
    });
    timeline.appendChild(pill);
  });
}

function _updateTimeline(activeIdx) {
  if (!timeline) return;
  const pills = timeline.querySelectorAll('.chord-pill');
  pills.forEach((p, i) => {
    p.classList.remove('active', 'near');
    if (i === activeIdx) p.classList.add('active');
    else if (Math.abs(i - activeIdx) <= 2) p.classList.add('near');
  });
  // Scroll active pill into view
  if (activeIdx >= 0 && pills[activeIdx]) {
    pills[activeIdx].scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  }
}

// ── Chord diagram render ─────────────────────────────────────
function _renderDiag(container, chordName, maxVoicings) {
  if (!container) return;
  if (!chordName || chordName === '—' || chordName === 'N.C.') {
    container.innerHTML = '';
    return;
  }
  if (window.getVoicings) {
    const voicings = window.getVoicings(chordName);
    if (voicings && window._chordSVG) {
      container.innerHTML = voicings.slice(0, maxVoicings).map(v =>
        `<div class="chord-diagram-wrap">${window._chordSVG(v, chordName)}<div class="chord-diagram-label">${v.label||''}</div></div>`
      ).join('');
      return;
    }
  }
  container.innerHTML = '';
}

// ── Apply transpose ──────────────────────────────────────────
function _applyTranspose() {
  // Tab content
  document.querySelectorAll('#tab-content .tab-bar').forEach(el => {
    if (el.dataset.orig !== undefined) el.textContent = _shiftTabText(el.dataset.orig, _transposeSteps);
  });
  document.querySelectorAll('.tab-chord-line').forEach(span => {
    const orig = span.dataset.origChordLine || span.textContent;
    span.dataset.origChordLine = orig;
    span.textContent = orig.replace(
      /\b([A-G][#b]?(?:m(?:aj7?|7b5)?|7|maj7|sus[24]|dim7?|aug)?)\b/g,
      name => _transposeChordName(name, _transposeSteps)
    );
  });
  // Rebuild timeline with transposed labels
  _buildTimeline();
  // Re-sync current display
  if (_lastActiveIdx >= 0) _updateTrinity(_lastActiveIdx);
  // Transpose display
  const disp = document.getElementById('tp-display');
  if (disp) disp.textContent = _transposeSteps === 0 ? '0' : (_transposeSteps > 0 ? `+${_transposeSteps}` : `${_transposeSteps}`);
}

function _barLabel(idx) {
  if (idx < 0 || idx >= _bars.length) return '—';
  return _transposeChordName(_bars[idx].label || 'N.C.', _transposeSteps);
}

function _updateTrinity(activeIdx) {
  _lastActiveIdx = activeIdx;
  const before = _barLabel(activeIdx - 1);
  const now    = _barLabel(activeIdx);
  const next   = _barLabel(activeIdx + 1);
  const after  = _barLabel(activeIdx + 2);

  if (elBefore) elBefore.textContent = before;
  if (elNow)    elNow.textContent    = now;
  if (elNext)   elNext.textContent   = next;
  if (elAfter)  elAfter.textContent  = after;

  // Diagrams: 2 voicings for NOW, 1 for NEXT, none for BEFORE/AFTER
  _renderDiag(diagNow,  now,  2);
  _renderDiag(diagNext, next, 1);
  if (diagBefore) diagBefore.innerHTML = '';
  if (diagAfter)  diagAfter.innerHTML  = '';

  // Legacy support if something calls updateChordDisplay
  if (window.updateChordDisplay) window.updateChordDisplay(now);
}

// ── Init ─────────────────────────────────────────────────────
function initPlayback(audioEl, bars, sections) {
  _lastActiveIdx = -2;
  _sections = sections || [];
  if (_initialized) {
    _audio = audioEl;
    _bars = bars || [];
    _tabBarCache = null;
    _transposeSteps = 0;
    _speed = 1.0;
    if (_audio) _audio.playbackRate = 1.0;
    document.querySelectorAll('.speed-btn').forEach(b => b.classList.toggle('active', b.dataset.speed === '1'));
    _buildTimeline();
    _applyTranspose();
    return;
  }

  _audio = audioEl;
  _bars = bars || [];
  _tabBarCache = null;
  _transposeSteps = 0;
  _speed = 1.0;
  if (_audio) _audio.playbackRate = 1.0;
  document.querySelectorAll('.speed-btn').forEach(b => b.classList.toggle('active', b.dataset.speed === '1'));
  _buildTimeline();
  _applyTranspose();

  _audio.addEventListener('play',  _onPlay);
  _audio.addEventListener('pause', _onPause);
  _audio.addEventListener('ended', _onPause);
  _audio.addEventListener('loadedmetadata', () => { _updateTime(); _buildSectionTimeline(); });

  playBtn.addEventListener('click', _togglePlay);

  const rewindBtn = document.getElementById('rewind-btn');
  const back5Btn  = document.getElementById('back5-btn');
  if (rewindBtn && !rewindBtn._bound) {
    rewindBtn._bound = true;
    rewindBtn.addEventListener('click', () => {
      if (!_audio) return;
      _audio.currentTime = 0;
      _updateTime();
      _syncTab();
    });
  }
  if (back5Btn && !back5Btn._bound) {
    back5Btn._bound = true;
    back5Btn.addEventListener('click', () => {
      if (!_audio) return;
      _audio.currentTime = Math.max(0, _audio.currentTime - 5);
      _updateTime();
      _syncTab();
    });
  }

  scrubber.addEventListener('click', e => {
    if (!_audio || !_audio.duration) return;
    const rect = scrubber.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    _audio.currentTime = frac * _audio.duration;
  });

  // Transpose buttons
  const tpM2 = document.getElementById('tp-m2');
  const tpM1 = document.getElementById('tp-m1');
  const tpP1 = document.getElementById('tp-p1');
  const tpP2 = document.getElementById('tp-p2');
  if (tpM2 && !tpM2._bound) {
    tpM2._bound = true;
    tpM2.addEventListener('click', () => { _transposeSteps -= 2; _applyTranspose(); });
    tpM1.addEventListener('click', () => { _transposeSteps -= 1; _applyTranspose(); });
    tpP1.addEventListener('click', () => { _transposeSteps += 1; _applyTranspose(); });
    tpP2.addEventListener('click', () => { _transposeSteps += 2; _applyTranspose(); });
  }

  // Speed buttons
  document.querySelectorAll('.speed-btn').forEach(btn => {
    if (btn._bound) return;
    btn._bound = true;
    btn.addEventListener('click', () => {
      _speed = parseFloat(btn.dataset.speed);
      if (_audio) _audio.playbackRate = _speed;
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.toggle('active', b === btn));
    });
  });

  _initialized = true;
}

function _togglePlay() {
  if (!_audio) return;
  _audio.paused ? _audio.play() : _audio.pause();
}

function _onPlay() {
  playIcon.innerHTML = '<div class="pause-bars"><div class="pause-bar"></div><div class="pause-bar"></div></div>';
  _tick();
}

function _onPause() {
  playIcon.innerHTML = '';
  playIcon.className = 'play-triangle';
  if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
}

function _tick() {
  _updateTime();
  _syncTab();
  _rafId = requestAnimationFrame(_tick);
}

function _updateTime() {
  if (!_audio) return;
  const cur = _audio.currentTime || 0;
  const dur = _audio.duration || 0;
  scrubFill.style.width = dur > 0 ? `${(cur / dur) * 100}%` : '0%';
  timeDisplay.textContent = `${_fmt(cur)} / ${_fmt(dur)}`;
}

function _fmt(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

function _syncTab() {
  if (!_audio || !_bars.length) return;
  const t = _audio.currentTime;

  let activeIdx = -1;
  for (let i = 0; i < _bars.length; i++) {
    if (t >= _bars[i].start_sec && t < _bars[i].end_sec) { activeIdx = i; break; }
  }
  if (activeIdx === -1 && t >= _bars[_bars.length - 1].end_sec) activeIdx = _bars.length - 1;

  // Only update DOM when bar changes
  if (activeIdx !== _lastActiveIdx) {
    if (activeIdx >= 0) _updateTrinity(activeIdx);
    _updateTimeline(activeIdx);
  }

  // Tab bar highlight
  const track = window.getActiveTab ? window.getActiveTab() : 'guitar1';
  if (track === 'drums') return;
  if (!_tabBarCache) _tabBarCache = document.querySelectorAll('#tab-content .tab-bar');
  const tabBars = _tabBarCache;
  if (!tabBars.length) return;
  tabBars.forEach((el, i) => {
    el.classList.remove('active', 'dim');
    if (i === activeIdx) { el.classList.add('active'); el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
    else if (activeIdx >= 0) el.classList.add('dim');
  });
}

window.initPlayback = initPlayback;

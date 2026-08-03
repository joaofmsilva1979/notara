/* Notara — playback bar + synchronized tab highlight */

let _audio = null;
let _bars = [];
let _rafId = null;
let _initialized = false;
let _tabBarCache = null;
let _transposeSteps = 0;  // semitones offset from original
let _speed = 1.0;

const playBtn     = document.getElementById('play-btn');
const playIcon    = document.getElementById('play-icon');
const scrubber    = document.getElementById('scrubber');
const scrubFill   = document.getElementById('scrubber-fill');
const timeDisplay = document.getElementById('time-display');
const chordNow    = document.getElementById('chord-now');
const chordNext   = document.getElementById('chord-next');

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
    // Tab string line: starts with note name(s) + pipe, e.g. e|, B|, F#|, G#|
    if (/^[A-Ga-g][#b]?\|/.test(line)) {
      return line.replace(/\d+/g, n => Math.max(0, parseInt(n) + steps).toString());
    }
    // Chord label line (first non-empty non-comment line of a bar block)
    if (/^[A-G]/.test(line.trim()) && !line.trim().startsWith('#')) {
      return _transposeChordName(line.trim(), steps);
    }
    return line;
  }).join('\n');
}

function _applyTranspose() {
  document.querySelectorAll('#tab-content .tab-bar').forEach(el => {
    if (el.dataset.orig !== undefined) {
      el.textContent = _shiftTabText(el.dataset.orig, _transposeSteps);
    }
  });
  // Transpose chord annotation lines in lyrics tab
  document.querySelectorAll('.tab-chord-line').forEach(span => {
    const orig = span.dataset.origChordLine || span.textContent;
    span.dataset.origChordLine = orig;
    span.textContent = orig.replace(
      /\b([A-G][#b]?(?:m(?:aj7?|7b5)?|7|maj7|sus[24]|dim7?|aug)?)\b/g,
      name => _transposeChordName(name, _transposeSteps)
    );
  });
  // Update chord display
  const raw = chordNow.dataset.rawChord || chordNow.textContent;
  chordNow.dataset.rawChord = raw;
  const shifted = _transposeChordName(raw, _transposeSteps);
  chordNow.textContent = shifted;
  if (window.updateChordDisplay) window.updateChordDisplay(shifted);
  // Update transpose display
  const disp = document.getElementById('tp-display');
  if (disp) {
    const semis = _transposeSteps;
    disp.textContent = semis === 0 ? '0' : (semis > 0 ? `+${semis}` : `${semis}`);
  }
}

// ── Init ─────────────────────────────────────────────────────
function initPlayback(audioEl, bars) {
  chordNow.textContent = chordNext.textContent = '—';
  chordNow.dataset.rawChord = '—';

  if (_initialized) {
    _audio = audioEl;
    _bars = bars || [];
    _tabBarCache = null;
    // Reset practice state on new track
    _transposeSteps = 0;
    _speed = 1.0;
    if (_audio) _audio.playbackRate = 1.0;
    document.querySelectorAll('.speed-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.speed === '1')
    );
    _applyTranspose();
    return;
  }

  _audio = audioEl;
  _bars = bars || [];
  _tabBarCache = null;

  // Reset practice state on first init
  _transposeSteps = 0;
  _speed = 1.0;
  if (_audio) _audio.playbackRate = 1.0;
  document.querySelectorAll('.speed-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.speed === '1')
  );
  _applyTranspose();

  _audio.addEventListener('play',  _onPlay);
  _audio.addEventListener('pause', _onPause);
  _audio.addEventListener('ended', _onPause);
  _audio.addEventListener('loadedmetadata', _updateTime);

  playBtn.addEventListener('click', _togglePlay);

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
  if (_audio.paused) {
    _audio.play();
  } else {
    _audio.pause();
  }
}

function _onPlay() {
  playIcon.innerHTML = '<div class="pause-bars"><div class="pause-bar"></div><div class="pause-bar"></div></div>';
  _tick();
}

function _onPause() {
  playIcon.innerHTML = '';
  playIcon.className = 'play-triangle';
  if (_rafId) {
    cancelAnimationFrame(_rafId);
    _rafId = null;
  }
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

  // Find active bar index
  let activeIdx = -1;
  for (let i = 0; i < _bars.length; i++) {
    if (t >= _bars[i].start_sec && t < _bars[i].end_sec) {
      activeIdx = i;
      break;
    }
  }

  // Clamp to last bar at end of track
  if (activeIdx === -1 && _bars.length > 0 && t >= _bars[_bars.length - 1].end_sec) {
    activeIdx = _bars.length - 1;
  }

  // Update chord display
  if (activeIdx >= 0) {
    const label = _bars[activeIdx].label || '—';
    const rawPrev = chordNow.dataset.rawChord || chordNow.textContent;
    if (rawPrev !== label) {
      chordNow.dataset.rawChord = label;
      const shifted = _transposeChordName(label, _transposeSteps);
      chordNow.textContent = shifted;
      if (window.updateChordDisplay) window.updateChordDisplay(shifted);
    }
    chordNext.textContent = _transposeChordName(
      activeIdx + 1 < _bars.length ? _bars[activeIdx + 1].label : '—',
      _transposeSteps
    );
  }

  // Highlight tab bar — only for guitar/bass/vocals (not drums)
  const track = window.getActiveTab ? window.getActiveTab() : 'guitar1';
  if (track === 'drums') return;

  if (!_tabBarCache) {
    _tabBarCache = document.querySelectorAll('#tab-content .tab-bar');
  }
  const tabBars = _tabBarCache;
  if (!tabBars.length) return;

  tabBars.forEach((el, i) => {
    el.classList.remove('active', 'dim');
    if (i === activeIdx) {
      el.classList.add('active');
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else if (activeIdx >= 0) {
      el.classList.add('dim');
    }
  });
}

window.initPlayback = initPlayback;

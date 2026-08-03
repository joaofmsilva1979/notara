/* Notara — playback bar + synchronized tab highlight */

let _audio = null;
let _bars = [];
let _rafId = null;

const playBtn     = document.getElementById('play-btn');
const playIcon    = document.getElementById('play-icon');
const scrubber    = document.getElementById('scrubber');
const scrubFill   = document.getElementById('scrubber-fill');
const timeDisplay = document.getElementById('time-display');
const chordNow    = document.getElementById('chord-now');
const chordNext   = document.getElementById('chord-next');

function initPlayback(audioEl, bars) {
  _audio = audioEl;
  _bars = bars || [];

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
  if (_rafId) cancelAnimationFrame(_rafId);
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

  // Update chord display
  if (activeIdx >= 0) {
    chordNow.textContent = _bars[activeIdx].label || '—';
    chordNext.textContent = activeIdx + 1 < _bars.length ? _bars[activeIdx + 1].label : '—';
  }

  // Highlight tab bar — only for guitar/bass/vocals (not drums)
  const track = window.getActiveTab ? window.getActiveTab() : 'guitar1';
  if (track === 'drums') return;

  const tabBars = document.querySelectorAll('#tab-content .tab-bar');
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

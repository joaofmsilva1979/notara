/* Notara — guitar chord diagram database + SVG renderer */

// frets[0]=low-E(6th), frets[5]=high-e(1st). -1=muted, 0=open, N=fret
// barre: fret number where the full barre is (all strings from that fret)
// label: optional position label
const CHORD_DB = {
  "C":     [{frets:[-1,3,2,0,1,0], label:"open"}, {frets:[-1,3,5,5,5,3], barre:3, label:"3fr"}],
  "Cm":    [{frets:[-1,3,5,5,4,3], barre:3, label:"3fr"}],
  "C7":    [{frets:[-1,3,2,3,1,0], label:"open"}],
  "Cmaj7": [{frets:[-1,3,2,0,0,0], label:"open"}],
  "Cm7":   [{frets:[-1,3,5,3,4,3], barre:3, label:"3fr"}],
  "Csus2": [{frets:[-1,3,5,5,3,3], barre:3, label:"3fr"}],
  "Csus4": [{frets:[-1,3,3,0,1,1], label:"open"}],
  "Cdim":  [{frets:[-1,3,4,5,4,-1], label:"3fr"}],
  "Caug":  [{frets:[-1,3,2,1,1,0], label:"open"}],

  "C#":    [{frets:[-1,4,6,6,6,4], barre:4, label:"4fr"}],
  "C#m":   [{frets:[-1,4,6,6,5,4], barre:4, label:"4fr"}],
  "C#7":   [{frets:[-1,4,3,4,2,0], label:"open"}],
  "C#maj7":[{frets:[-1,4,6,5,6,4], barre:4, label:"4fr"}],
  "C#m7":  [{frets:[-1,4,6,4,5,4], barre:4, label:"4fr"}],
  "C#sus2":[{frets:[-1,4,6,6,4,4], barre:4, label:"4fr"}],
  "C#sus4":[{frets:[-1,4,4,6,7,4], barre:4, label:"4fr"}],

  "D":     [{frets:[-1,-1,0,2,3,2], label:"open"}, {frets:[5,5,7,7,7,5], barre:5, label:"5fr"}],
  "Dm":    [{frets:[-1,-1,0,2,3,1], label:"open"}, {frets:[5,5,7,7,6,5], barre:5, label:"5fr"}],
  "D7":    [{frets:[-1,-1,0,2,1,2], label:"open"}],
  "Dmaj7": [{frets:[-1,-1,0,2,2,2], label:"open"}],
  "Dm7":   [{frets:[-1,-1,0,2,1,1], label:"open"}],
  "Dsus2": [{frets:[-1,-1,0,2,3,0], label:"open"}, {frets:[5,5,7,7,5,5], barre:5, label:"5fr"}],
  "Dsus4": [{frets:[-1,-1,0,2,3,3], label:"open"}],
  "Ddim":  [{frets:[-1,-1,0,1,3,1], label:"open"}],
  "Daug":  [{frets:[-1,-1,0,3,3,2], label:"open"}],

  "D#":    [{frets:[-1,6,8,8,8,6], barre:6, label:"6fr"}],
  "D#m":   [{frets:[-1,6,8,8,7,6], barre:6, label:"6fr"}],
  "D#7":   [{frets:[-1,6,5,6,4,4], barre:4, label:"4fr"}],
  "D#maj7":[{frets:[-1,6,8,7,8,6], barre:6, label:"6fr"}],
  "D#m7":  [{frets:[-1,6,8,6,7,6], barre:6, label:"6fr"}],
  "D#sus2":[{frets:[-1,6,8,8,6,6], barre:6, label:"6fr"}],
  "D#sus4":[{frets:[-1,6,6,8,9,6], barre:6, label:"6fr"}],

  "E":     [{frets:[0,2,2,1,0,0], label:"open"}, {frets:[7,7,9,9,9,7], barre:7, label:"7fr"}],
  "Em":    [{frets:[0,2,2,0,0,0], label:"open"}, {frets:[7,7,9,9,8,7], barre:7, label:"7fr"}],
  "E7":    [{frets:[0,2,0,1,0,0], label:"open"}],
  "Emaj7": [{frets:[0,2,1,1,0,0], label:"open"}],
  "Em7":   [{frets:[0,2,0,0,0,0], label:"open"}],
  "Esus2": [{frets:[0,2,2,4,0,0], label:"open"}],
  "Esus4": [{frets:[0,2,2,2,0,0], label:"open"}],
  "Edim":  [{frets:[0,1,2,3,2,-1], label:"open"}],
  "Eaug":  [{frets:[0,3,2,1,1,0], label:"open"}],

  "F":     [{frets:[1,1,2,3,3,1], barre:1, label:"1fr"}, {frets:[8,8,10,10,10,8], barre:8, label:"8fr"}],
  "Fm":    [{frets:[1,3,3,1,1,1], barre:1, label:"1fr"}],
  "F7":    [{frets:[1,1,2,1,3,1], barre:1, label:"1fr"}],
  "Fmaj7": [{frets:[-1,-1,3,2,1,0], label:"open"}, {frets:[1,3,3,2,1,1], barre:1, label:"1fr"}],
  "Fm7":   [{frets:[1,3,1,1,1,1], barre:1, label:"1fr"}],
  "Fsus2": [{frets:[-1,-1,3,0,1,1], label:"open"}],
  "Fsus4": [{frets:[1,3,3,3,1,1], barre:1, label:"1fr"}],
  "Fdim":  [{frets:[-1,-1,3,4,3,1], label:"open"}],
  "Faug":  [{frets:[-1,-1,3,2,2,1], label:"open"}],

  "F#":    [{frets:[2,2,4,4,4,2], barre:2, label:"2fr"}],
  "F#m":   [{frets:[2,4,4,2,2,2], barre:2, label:"2fr"}],
  "F#7":   [{frets:[2,2,4,3,4,2], barre:2, label:"2fr"}],
  "F#maj7":[{frets:[2,4,3,3,2,2], barre:2, label:"2fr"}],
  "F#m7":  [{frets:[2,4,2,2,2,2], barre:2, label:"2fr"}],
  "F#sus2":[{frets:[2,4,4,1,2,2], barre:2, label:"2fr"}],
  "F#sus4":[{frets:[2,4,4,4,2,2], barre:2, label:"2fr"}],

  "G":     [{frets:[3,2,0,0,0,3], label:"open"}, {frets:[3,5,5,4,3,3], barre:3, label:"3fr"}],
  "Gm":    [{frets:[3,5,5,3,3,3], barre:3, label:"3fr"}],
  "G7":    [{frets:[3,2,0,0,0,1], label:"open"}],
  "Gmaj7": [{frets:[3,2,0,0,0,2], label:"open"}],
  "Gm7":   [{frets:[3,5,3,3,3,3], barre:3, label:"3fr"}],
  "Gsus2": [{frets:[3,5,5,0,3,3], label:"open"}],
  "Gsus4": [{frets:[3,3,0,0,1,3], label:"open"}],
  "Gdim":  [{frets:[3,4,5,3,-1,-1], label:"3fr"}],
  "Gaug":  [{frets:[3,2,1,0,0,-1], label:"open"}],

  "G#":    [{frets:[4,4,6,6,6,4], barre:4, label:"4fr"}],
  "G#m":   [{frets:[4,6,6,4,4,4], barre:4, label:"4fr"}],
  "G#7":   [{frets:[4,4,6,5,6,4], barre:4, label:"4fr"}],
  "G#maj7":[{frets:[4,6,5,5,4,4], barre:4, label:"4fr"}],
  "G#m7":  [{frets:[4,6,4,4,4,4], barre:4, label:"4fr"}],
  "G#sus2":[{frets:[4,6,6,3,4,4], barre:4, label:"4fr"}],
  "G#sus4":[{frets:[4,6,6,6,4,4], barre:4, label:"4fr"}],

  "A":     [{frets:[-1,0,2,2,2,0], label:"open"}, {frets:[5,5,7,7,7,5], barre:5, label:"5fr"}],
  "Am":    [{frets:[-1,0,2,2,1,0], label:"open"}, {frets:[5,7,7,5,5,5], barre:5, label:"5fr"}],
  "A7":    [{frets:[-1,0,2,0,2,0], label:"open"}],
  "Amaj7": [{frets:[-1,0,2,1,2,0], label:"open"}],
  "Am7":   [{frets:[-1,0,2,0,1,0], label:"open"}],
  "Asus2": [{frets:[-1,0,2,2,0,0], label:"open"}],
  "Asus4": [{frets:[-1,0,2,2,3,0], label:"open"}],
  "Adim":  [{frets:[-1,0,1,2,1,-1], label:"open"}],
  "Aaug":  [{frets:[-1,0,3,2,2,1], label:"open"}],
  "Am7b5": [{frets:[-1,0,1,2,1,3], label:"open"}],

  "A#":    [{frets:[-1,1,3,3,3,1], barre:1, label:"1fr"}, {frets:[6,6,8,8,8,6], barre:6, label:"6fr"}],
  "A#m":   [{frets:[-1,1,3,3,2,1], barre:1, label:"1fr"}],
  "A#7":   [{frets:[-1,1,3,1,3,1], barre:1, label:"1fr"}],
  "A#maj7":[{frets:[-1,1,3,2,3,1], barre:1, label:"1fr"}],
  "A#m7":  [{frets:[-1,1,3,1,2,1], barre:1, label:"1fr"}],
  "A#sus2":[{frets:[-1,1,3,3,1,1], barre:1, label:"1fr"}],
  "A#sus4":[{frets:[-1,1,1,3,4,1], barre:1, label:"1fr"}],

  "B":     [{frets:[-1,2,4,4,4,2], barre:2, label:"2fr"}, {frets:[7,7,9,9,9,7], barre:7, label:"7fr"}],
  "Bm":    [{frets:[-1,2,4,4,3,2], barre:2, label:"2fr"}],
  "B7":    [{frets:[-1,2,1,2,0,2], label:"open"}],
  "Bmaj7": [{frets:[-1,2,4,3,4,2], barre:2, label:"2fr"}],
  "Bm7":   [{frets:[-1,2,4,2,3,2], barre:2, label:"2fr"}],
  "Bsus2": [{frets:[-1,2,4,4,2,2], barre:2, label:"2fr"}],
  "Bsus4": [{frets:[-1,2,4,4,5,2], barre:2, label:"2fr"}],
  "Bdim":  [{frets:[-1,2,3,4,3,-1], label:"2fr"}],
  "Baug":  [{frets:[-1,2,1,0,0,-1], label:"open"}],
  "Bm7b5": [{frets:[-1,2,3,2,3,2], barre:2, label:"2fr"}],
};

// Enharmonic equivalents
const CHORD_ALIASES = {
  "Db": "C#", "Dbm": "C#m", "Dbmaj7": "C#maj7", "Dbm7": "C#m7",
  "Eb": "D#", "Ebm": "D#m", "Ebmaj7": "D#maj7", "Ebm7": "D#m7",
  "Gb": "F#", "Gbm": "F#m", "Gbmaj7": "F#maj7", "Gbm7": "F#m7",
  "Ab": "G#", "Abm": "G#m", "Abmaj7": "G#maj7", "Abm7": "G#m7",
  "Bb": "A#", "Bbm": "A#m", "Bbmaj7": "A#maj7", "Bbm7": "A#m7",
};

function getVoicings(chordName) {
  const name = CHORD_ALIASES[chordName] || chordName;
  return CHORD_DB[name] || null;
}

function _chordSVG(voicing, chordName) {
  const frets = voicing.frets;   // [e6, a5, d4, g3, b2, e1]
  const barre = voicing.barre || null;
  const label = voicing.label || '';

  // Layout constants
  const W = 82, H = 108;
  const nameH = 16, markerH = 14, xoH = 14;
  const pL = 10, pR = 10;
  const gridW = W - pL - pR;
  const STRINGS = 6, FRETS = 5;
  const sSpacing = gridW / (STRINGS - 1);  // space between strings
  const fretSpacing = (H - nameH - markerH - xoH - 6) / FRETS;

  const gridTop = nameH + markerH + xoH;
  const nutY = gridTop;

  // Is this an open-position chord (all frets ≤ 5)?
  const playedFrets = frets.filter(f => f > 0);
  const isOpen = !barre && (playedFrets.length === 0 || Math.min(...playedFrets) <= 5);
  const startFret = barre ? barre : (playedFrets.length ? Math.min(...playedFrets) : 1);

  const sx = (i) => pL + i * sSpacing;  // x for string i (0=low E)
  const fy = (f) => {
    const relFret = isOpen ? f : (f - startFret + 1);
    return nutY + (relFret - 0.5) * fretSpacing;
  };

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;

  // Chord name
  svg += `<text x="${W/2}" y="${nameH - 2}" text-anchor="middle" font-family="Helvetica Neue,Helvetica,Arial,sans-serif" font-size="11" font-weight="700" fill="#1a1a1a">${chordName}</text>`;

  // Fret position label (e.g. "5fr") — only for barre chords not at fret 1
  if (barre && barre > 1) {
    svg += `<text x="${W - 4}" y="${gridTop + fretSpacing * 0.8}" text-anchor="end" font-family="Helvetica Neue,Helvetica,Arial,sans-serif" font-size="8" fill="#888">${barre}fr</text>`;
  }

  // Nut (thick line at fret 0 for open chords starting at fret 1)
  if (isOpen || startFret === 1) {
    svg += `<rect x="${pL}" y="${nutY - 2}" width="${gridW}" height="4" rx="2" fill="#1a1a1a"/>`;
  }

  // Fret lines (horizontal)
  for (let f = 1; f <= FRETS; f++) {
    const y = nutY + f * fretSpacing;
    svg += `<line x1="${pL}" y1="${y}" x2="${pL + gridW}" y2="${y}" stroke="#ccc" stroke-width="1"/>`;
  }

  // String lines (vertical)
  for (let s = 0; s < STRINGS; s++) {
    const x = sx(s);
    svg += `<line x1="${x}" y1="${nutY}" x2="${x}" y2="${nutY + FRETS * fretSpacing}" stroke="#888" stroke-width="1"/>`;
  }

  // X/O above strings
  for (let s = 0; s < STRINGS; s++) {
    const x = sx(s);
    const y = nutY - 4;
    if (frets[s] === -1) {
      svg += `<text x="${x}" y="${y}" text-anchor="middle" font-family="Helvetica Neue,Arial,sans-serif" font-size="9" fill="#cc3333">✕</text>`;
    } else if (frets[s] === 0) {
      svg += `<circle cx="${x}" cy="${y - 4}" r="3.5" fill="none" stroke="#555" stroke-width="1.2"/>`;
    }
  }

  // Barre indicator
  if (barre) {
    const barreY = fy(barre);
    // Find leftmost and rightmost string in the barre (non-muted)
    const barreFretStrings = frets.map((f, i) => ({f, i})).filter(({f}) => f !== -1).map(({i}) => i);
    if (barreFretStrings.length >= 2) {
      const x1 = sx(barreFretStrings[0]);
      const x2 = sx(barreFretStrings[barreFretStrings.length - 1]);
      svg += `<rect x="${x1 - 5}" y="${barreY - 5}" width="${x2 - x1 + 10}" height="10" rx="5" fill="#1a1a1a"/>`;
    }
  }

  // Finger dots
  for (let s = 0; s < STRINGS; s++) {
    const f = frets[s];
    if (f > 0 && f !== barre) {
      const x = sx(s);
      const y = fy(f);
      svg += `<circle cx="${x}" cy="${y}" r="6" fill="#B71C1C"/>`;
    }
  }

  svg += `</svg>`;
  return svg;
}

function updateChordDisplay(chordName) {
  const box = document.getElementById('chord-diagrams');
  if (!box) return;
  if (!chordName || chordName === '—') {
    box.innerHTML = '';
    return;
  }
  const voicings = getVoicings(chordName);
  if (!voicings) {
    box.innerHTML = '';
    return;
  }
  box.innerHTML = voicings.slice(0, 2).map(v =>
    `<div class="chord-diagram-wrap">
      ${_chordSVG(v, chordName)}
      <div class="chord-diagram-label">${v.label || ''}</div>
    </div>`
  ).join('');
}

window.updateChordDisplay = updateChordDisplay;

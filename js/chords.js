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

  // ── add9 (major triad + 9th, no 7th) ────────────────────────────────────
  "Cadd9":  [{frets:[-1,3,2,0,3,3], label:"open"}],
  "C#add9": [{frets:[4,4,6,6,6,6], barre:4, label:"4fr"}],
  "Dadd9":  [{frets:[-1,-1,0,2,3,0], label:"open"}],
  "D#add9": [{frets:[6,6,8,8,8,8], barre:6, label:"6fr"}],
  "Eadd9":  [{frets:[0,2,2,1,0,2], label:"open"}],
  "Fadd9":  [{frets:[1,1,3,3,3,3], barre:1, label:"1fr"}],
  "F#add9": [{frets:[2,2,4,4,4,4], barre:2, label:"2fr"}],
  "Gadd9":  [{frets:[3,2,0,0,3,3], label:"open"}],
  "G#add9": [{frets:[4,4,6,6,6,6], barre:4, label:"4fr"}],
  "Aadd9":  [{frets:[-1,0,2,4,2,0], label:"open"}, {frets:[5,5,7,7,7,7], barre:5, label:"5fr"}],
  "A#add9": [{frets:[6,6,8,8,8,8], barre:6, label:"6fr"}],
  "Badd9":  [{frets:[-1,2,4,4,4,4], barre:2, label:"2fr"}],

  // ── madd9 (minor triad + 9th, no 7th) ───────────────────────────────────
  "Cmadd9":  [{frets:[-1,3,5,5,4,3], barre:3, label:"3fr"}],
  "C#madd9": [{frets:[-1,4,6,6,5,4], barre:4, label:"4fr"}],
  "Dmadd9":  [{frets:[-1,-1,0,2,3,1], label:"open"}],
  "D#madd9": [{frets:[6,6,8,8,7,6], barre:6, label:"6fr"}],
  "Emadd9":  [{frets:[0,2,2,0,0,2], label:"open"}],
  "Fmadd9":  [{frets:[1,3,3,1,1,3], barre:1, label:"1fr"}],
  "F#madd9": [{frets:[2,4,4,2,2,4], barre:2, label:"2fr"}],
  "Gmadd9":  [{frets:[3,5,5,3,3,5], barre:3, label:"3fr"}],
  "G#madd9": [{frets:[4,6,6,4,4,6], barre:4, label:"4fr"}],
  "Amadd9":  [{frets:[-1,0,2,2,1,2], label:"open"}],
  "A#madd9": [{frets:[6,8,8,6,6,8], barre:6, label:"6fr"}],
  "Bmadd9":  [{frets:[-1,2,4,4,3,4], barre:2, label:"2fr"}],

  // ── 9 (dominant 9: root + M3 + P5 + m7 + M9) ───────────────────────────
  "C9":  [{frets:[-1,3,2,3,3,3], barre:3, label:"3fr"}],
  "C#9": [{frets:[-1,4,3,4,4,4], barre:4, label:"4fr"}],
  "D9":  [{frets:[-1,-1,0,2,1,0], label:"open"}],
  "D#9": [{frets:[-1,6,5,6,6,6], barre:6, label:"6fr"}],
  "E9":  [{frets:[0,2,0,1,3,2], label:"open"}],
  "F9":  [{frets:[1,3,1,2,1,1], barre:1, label:"1fr"}],
  "F#9": [{frets:[2,4,2,3,2,2], barre:2, label:"2fr"}],
  "G9":  [{frets:[3,2,0,2,1,1], label:"open"}],
  "G#9": [{frets:[4,6,4,5,4,4], barre:4, label:"4fr"}],
  "A9":  [{frets:[-1,0,2,4,2,3], label:"open"}, {frets:[5,7,5,6,5,5], barre:5, label:"5fr"}],
  "A#9": [{frets:[-1,1,3,1,3,1], barre:1, label:"1fr"}],
  "B9":  [{frets:[-1,2,4,2,4,2], barre:2, label:"2fr"}],

  // ── m9 (minor 9: root + m3 + P5 + m7 + M9) ─────────────────────────────
  "Cm9":  [{frets:[-1,3,1,3,4,3], barre:3, label:"3fr"}],
  "C#m9": [{frets:[-1,4,2,4,5,4], barre:4, label:"4fr"}],
  "Dm9":  [{frets:[-1,-1,0,2,1,0], label:"open"}],
  "D#m9": [{frets:[6,6,8,6,7,6], barre:6, label:"6fr"}],
  "Em9":  [{frets:[0,2,0,0,3,0], label:"open"}],
  "Fm9":  [{frets:[1,3,1,1,4,1], barre:1, label:"1fr"}],
  "F#m9": [{frets:[2,4,2,2,5,2], barre:2, label:"2fr"}],
  "Gm9":  [{frets:[3,5,3,3,6,3], barre:3, label:"3fr"}],
  "G#m9": [{frets:[4,6,4,4,7,4], barre:4, label:"4fr"}],
  "Am9":  [{frets:[-1,0,2,0,1,0], label:"open"}],
  "A#m9": [{frets:[-1,1,3,1,2,1], barre:1, label:"1fr"}],
  "Bm9":  [{frets:[-1,2,4,2,3,2], barre:2, label:"2fr"}],

  // ── maj9 (major 9: root + M3 + P5 + M7 + M9) ───────────────────────────
  "Cmaj9":  [{frets:[-1,3,0,0,3,0], label:"open"}],
  "C#maj9": [{frets:[-1,4,6,5,4,4], barre:4, label:"4fr"}],
  "Dmaj9":  [{frets:[-1,-1,0,2,2,0], label:"open"}],
  "D#maj9": [{frets:[-1,6,8,7,6,6], barre:6, label:"6fr"}],
  "Emaj9":  [{frets:[0,2,1,1,0,2], label:"open"}],
  "Fmaj9":  [{frets:[-1,-1,3,2,1,3], label:"open"}],
  "F#maj9": [{frets:[2,4,3,3,2,4], barre:2, label:"2fr"}],
  "Gmaj9":  [{frets:[3,2,0,2,3,2], label:"open"}],
  "G#maj9": [{frets:[4,6,5,5,4,6], barre:4, label:"4fr"}],
  "Amaj9":  [{frets:[-1,0,2,1,2,2], label:"open"}],
  "A#maj9": [{frets:[-1,1,3,2,3,3], barre:1, label:"1fr"}],
  "Bmaj9":  [{frets:[-1,2,4,3,4,4], barre:2, label:"2fr"}],

  // ── mmaj7 (minor-major 7: root + m3 + P5 + M7) ──────────────────────────
  "Cmmaj7":  [{frets:[-1,3,5,4,4,3], barre:3, label:"3fr"}],
  "C#mmaj7": [{frets:[-1,4,6,5,5,4], barre:4, label:"4fr"}],
  "Dmmaj7":  [{frets:[-1,-1,0,2,2,1], label:"open"}],
  "D#mmaj7": [{frets:[6,6,8,7,7,6], barre:6, label:"6fr"}],
  "Emmaj7":  [{frets:[0,2,2,0,0,0], label:"open"}],  // close to Em with open B
  "Fmmaj7":  [{frets:[1,3,3,1,1,0], barre:1, label:"1fr"}],
  "F#mmaj7": [{frets:[2,4,4,2,2,1], barre:2, label:"2fr"}],
  "Gmmaj7":  [{frets:[3,5,5,3,3,2], barre:3, label:"3fr"}],
  "G#mmaj7": [{frets:[4,6,6,4,4,3], barre:4, label:"4fr"}],
  "Ammaj7":  [{frets:[-1,0,2,1,1,0], label:"open"}],
  "A#mmaj7": [{frets:[-1,1,3,2,2,1], barre:1, label:"1fr"}],
  "Bmmaj7":  [{frets:[-1,2,4,3,3,2], barre:2, label:"2fr"}],

  // ── m6 (minor 6: root + m3 + P5 + M6) ──────────────────────────────────
  "Cm6":  [{frets:[-1,3,5,5,4,5], barre:3, label:"3fr"}],
  "C#m6": [{frets:[-1,4,6,6,5,6], barre:4, label:"4fr"}],
  "Dm6":  [{frets:[-1,-1,0,2,3,2], label:"open"}],
  "D#m6": [{frets:[6,6,8,8,7,8], barre:6, label:"6fr"}],
  "Em6":  [{frets:[0,2,2,0,2,0], label:"open"}],
  "Fm6":  [{frets:[1,3,3,1,3,1], barre:1, label:"1fr"}],
  "F#m6": [{frets:[2,4,4,2,4,2], barre:2, label:"2fr"}],
  "Gm6":  [{frets:[3,5,5,3,5,3], barre:3, label:"3fr"}],
  "G#m6": [{frets:[4,6,6,4,6,4], barre:4, label:"4fr"}],
  "Am6":  [{frets:[-1,0,2,2,1,2], label:"open"}],
  "A#m6": [{frets:[-1,1,3,3,2,3], barre:1, label:"1fr"}],
  "Bm6":  [{frets:[-1,2,4,4,3,4], barre:2, label:"2fr"}],

  // ── 6/9 (root + M3 + P5 + M6 + M9) ─────────────────────────────────────
  "C6/9":  [{frets:[-1,3,2,2,3,3], label:"open"}],
  "D6/9":  [{frets:[-1,-1,0,2,0,2], label:"open"}],
  "E6/9":  [{frets:[0,2,2,1,2,2], label:"open"}],
  "G6/9":  [{frets:[3,2,0,2,0,0], label:"open"}],
  "A6/9":  [{frets:[-1,0,2,2,2,2], label:"open"}],

  // ── 13 (dominant 13: root + M3 + m7 + M13) ──────────────────────────────
  "C13":  [{frets:[-1,3,2,3,3,5], label:"open"}],
  "D13":  [{frets:[-1,5,4,5,5,7], barre:5, label:"5fr"}],
  "E13":  [{frets:[0,2,0,1,2,2], label:"open"}],
  "G13":  [{frets:[3,2,0,0,1,3], label:"open"}],
  "A13":  [{frets:[-1,0,2,0,2,2], label:"open"}],
  "B13":  [{frets:[-1,2,1,2,0,2], label:"open"}],

  // ── 7b9 (dominant 7 flat 9) ──────────────────────────────────────────────
  "C7b9":  [{frets:[-1,3,2,3,2,3], label:"3fr"}],
  "D7b9":  [{frets:[-1,-1,0,2,1,3], label:"open"}],
  "E7b9":  [{frets:[0,2,0,1,0,1], label:"open"}],
  "F7b9":  [{frets:[1,1,2,1,2,2], barre:1, label:"1fr"}],
  "G7b9":  [{frets:[3,2,0,1,0,1], label:"open"}],
  "A7b9":  [{frets:[-1,0,2,0,2,1], label:"open"}],
  "B7b9":  [{frets:[-1,2,1,2,1,3], label:"2fr"}],

  // ── 7#9 (dominant 7 sharp 9 — "Hendrix chord") ──────────────────────────
  "E7#9":  [{frets:[0,2,2,1,3,3], label:"open"}],
  "A7#9":  [{frets:[-1,0,2,0,3,3], label:"open"}],
  "B7#9":  [{frets:[-1,2,1,2,3,3], label:"2fr"}],
  "C7#9":  [{frets:[-1,3,2,3,4,4], label:"3fr"}],
  "D7#9":  [{frets:[-1,-1,0,2,1,3], label:"open"}],
  "G7#9":  [{frets:[3,2,0,1,1,3], label:"open"}],

  // ── 7#11 (Lydian dominant) ────────────────────────────────────────────────
  "A7#11": [{frets:[-1,0,2,3,2,3], label:"open"}],
  "E7#11": [{frets:[0,2,0,3,0,2], label:"open"}],
  "G7#11": [{frets:[3,2,0,3,1,2], label:"open"}],
  "D7#11": [{frets:[-1,-1,0,3,1,2], label:"open"}],

  // ── maj7#11 (Lydian major) ────────────────────────────────────────────────
  "Cmaj7#11":  [{frets:[-1,3,2,2,2,0], label:"open"}],
  "Emaj7#11":  [{frets:[0,2,1,3,0,2], label:"open"}],
  "Gmaj7#11":  [{frets:[3,2,0,2,0,2], label:"open"}],
  "Amaj7#11":  [{frets:[-1,0,2,2,2,3], label:"open"}],

  // ── m11 (minor 11) ───────────────────────────────────────────────────────
  "Am11": [{frets:[-1,0,2,0,1,3], label:"open"}],
  "Em11": [{frets:[0,2,0,0,0,3], label:"open"}],
  "Dm11": [{frets:[-1,-1,0,2,1,3], label:"open"}],
  "Bm11": [{frets:[-1,2,4,2,3,5], barre:2, label:"2fr"}],
};

// Enharmonic equivalents + flat-name aliases for all new chord types
const CHORD_ALIASES = {
  "Db": "C#", "Dbm": "C#m", "Dbmaj7": "C#maj7", "Dbm7": "C#m7",
  "Eb": "D#", "Ebm": "D#m", "Ebmaj7": "D#maj7", "Ebm7": "D#m7",
  "Gb": "F#", "Gbm": "F#m", "Gbmaj7": "F#maj7", "Gbm7": "F#m7",
  "Ab": "G#", "Abm": "G#m", "Abmaj7": "G#maj7", "Abm7": "G#m7",
  "Bb": "A#", "Bbm": "A#m", "Bbmaj7": "A#maj7", "Bbm7": "A#m7",
  // flat add9/9/m9 aliases
  "Dbadd9":"C#add9","Dmadd9":"C#madd9","Db9":"C#9","Dbm9":"C#m9","Dbmaj9":"C#maj9",
  "Ebadd9":"D#add9","Ebmadd9":"D#madd9","Eb9":"D#9","Ebm9":"D#m9","Ebmaj9":"D#maj9",
  "Gbadd9":"F#add9","Gbmadd9":"F#madd9","Gb9":"F#9","Gbm9":"F#m9","Gbmaj9":"F#maj9",
  "Abadd9":"G#add9","Abmadd9":"G#madd9","Ab9":"G#9","Abm9":"G#m9","Abmaj9":"G#maj9",
  "Bbadd9":"A#add9","Bbmadd9":"A#madd9","Bb9":"A#9","Bbm9":"A#m9","Bbmaj9":"A#maj9",
};

// Fallback chain: if a chord has no voicing, try simpler forms
const CHORD_FALLBACK = {
  "add9": "",    "madd9": "m",
  "9": "7",      "m9": "m7",    "maj9": "maj7",
  "7b9": "7",    "7#9": "7",    "7#11": "7",   "13": "7",
  "maj7#11": "maj7",
  "m11": "m7",   "6/9": "6",    "mmaj7": "m",
};

function _parseChord(name) {
  // Returns {root, quality} or null
  const roots = ["C#","D#","F#","G#","A#","Db","Eb","Gb","Ab","Bb","C","D","E","F","G","A","B"];
  for (const r of roots) {
    if (name.startsWith(r)) return { root: r, quality: name.slice(r.length) };
  }
  return null;
}

function getVoicings(chordName) {
  const canonical = CHORD_ALIASES[chordName] || chordName;
  if (CHORD_DB[canonical]) return CHORD_DB[canonical];

  // Try fallback: downgrade to simpler quality
  const parsed = _parseChord(canonical);
  if (!parsed) return null;

  const { root, quality } = parsed;
  if (CHORD_FALLBACK[quality] !== undefined) {
    const simpler = (CHORD_ALIASES[root + CHORD_FALLBACK[quality]]) || (root + CHORD_FALLBACK[quality]);
    if (CHORD_DB[simpler]) return CHORD_DB[simpler];
    // One more level down if needed
    const parsed2 = _parseChord(simpler);
    if (parsed2 && CHORD_FALLBACK[parsed2.quality] !== undefined) {
      const simplest = parsed2.root + CHORD_FALLBACK[parsed2.quality];
      if (CHORD_DB[simplest]) return CHORD_DB[simplest];
    }
  }
  return null;
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
window.getVoicings = getVoicings;
window._chordSVG = _chordSVG;

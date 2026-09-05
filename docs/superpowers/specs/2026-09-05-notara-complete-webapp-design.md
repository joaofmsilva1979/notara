# Notara — Complete Web App Design

**Date:** 2026-09-05
**Scope:** Web app only (native Mac/iOS deferred)
**Approach:** Audit-first → Lyrics shipped → BTC+SynthTab integrated → Polish + Deploy

---

## 1. Context

Notara is a deployed web app (GitHub Pages + `api.notara.app`) that converts audio into guitar/bass/vocal/drum/keys tabs. As of 2026-09-05:

- **Committed and live:** multi-guitar, bass tab, PDF export, tuning detection, chord detection, web platform
- **Uncommitted (in progress):** lyrics+chords alignment (routes.py, worker.py, index.html, css/main.css, js/app.js modified; plan at `docs/superpowers/plans/2026-08-03-lyrics-chords.md`)
- **Experimental (not integrated):** `pipeline/btc/` (BTC chord model), `pipeline/synthtab/` (SynthTab transcription), `chord_detection_btc.py`, `transcription_synthtab.py`

---

## 2. Architecture — 4 Sprints

### Sprint 0 — Audit

Run all available audit tools before touching any code:

| Tool | What it covers |
|------|----------------|
| `claude-security:claude-security` | Vulnérabilités, injection, CORS, upload safety |
| `codebase-audit-suite` | Architecture, tests, docs, persistence |
| `sharp-edges:sharp-edges` | APIs dangereuses, defaults problématiques |
| `static-analysis:semgrep` | Analyse statique Python + JS |

**Output:** Findings classés en trois niveaux :
- **Critique** — bloque le sprint 1 (rien en prod avant fix)
- **Majeur** — traité dans le sprint 1
- **Mineur** — backlog, traité dans le sprint 3 ou après

### Sprint 1 — Fixes audit + Lyrics shipped

1. Appliquer tous les findings critiques et majeurs
2. Commiter les changements lyrics déjà en cours :
   - `pipeline/lyrics_align.py` (nouveau module)
   - `api/routes.py` — accept `lyrics_file` / `lyrics_text`
   - `api/worker.py` — call `align_lyrics` après chord detection
   - `index.html` + `css/main.css` — UI collapsible lyrics section
   - `js/app.js` — render "Lyrics" tab
   - `tests/test_lyrics_align.py`
3. Vérifier que `pytest` passe complètement avant de commiter

**Comportement en cas d'échec lyrics :** si `stable-whisper` échoue (mémoire, timeout), le job se termine normalement sans tab lyrics. Pas d'erreur globale propagée.

### Sprint 2 — BTC + SynthTab intégration

#### Nouveaux paramètres de job

```python
# api/jobs.py
chord_model: Literal["legacy", "btc"] = "btc"         # défaut = btc si import réussit ET poids présents
transcriber:  Literal["basic-pitch", "synthtab"] = "synthtab"  # défaut = synthtab si import réussit
```

"Disponible" = l'import du module réussit au démarrage du serveur (testé dans `api/main.py` lifespan). Si l'import échoue, le défaut bascule automatiquement sur `"legacy"` / `"basic-pitch"` pour tous les jobs de cette instance.

Exposés dans `POST /api/jobs` comme champs optionnels (`chord_model`, `transcriber`). Frontend : deux toggles discrets dans la section options avancées.

#### Fallback automatique

```
BTC disponible ? → utiliser BTC
BTC échoue (OOM, modèle absent, exception) → fallback legacy, log warning dans step_label
```

Pareil pour SynthTab → basic-pitch. Le job ne plante jamais à cause d'un module expérimental.

#### Benchmark qualité avant de fixer le défaut

Avant de basculer le défaut en production :

1. Dataset de référence : 5-10 fichiers WAV connus (tracks dont les tabs existent)
2. Métriques :
   - **Chord accuracy** : % de bars avec label correct (BTC vs legacy)
   - **Note precision/recall** : notes correctement transcrites (SynthTab vs basic-pitch)
3. Le défaut (`"btc"` / `"synthtab"`) n'est activé que si le benchmark montre une amélioration nette (> 5 points de pourcentage de précision sur le dataset de référence)
4. `tests/benchmark.py` est un **nouvel artefact à créer** dans le sprint 2 — script standalone qui itère sur le dataset, appelle les deux pipelines, et produit un rapport comparatif en console

#### Tests

Chaque wrapper a ses propres tests unitaires avec **mock du modèle ML** (les poids ne sont pas téléchargés en CI) :
- `tests/test_chord_detection_btc.py`
- `tests/test_transcription_synthtab.py`

### Sprint 3 — Polish + Deploy

1. **UX onboarding guidé** : dialog/tooltip avant traitement suggérant tuning, key, tempo si non renseignés (pattern existant dans l'UI, à étendre)
2. **Performance** : mise en cache des modèles Demucs entre jobs (éviter le rechargement à chaque job sur le même process)
3. **Deploy propre** : push vers `main`, vérifier `api.notara.app` opérationnel, run smoke tests manuels

---

## 3. Data Flow (inchangé structurellement)

```
Upload / YouTube URL
  → POST /api/jobs (+ chord_model, transcriber, lyrics optionnel)
  → worker.run_job
      1. Séparation Demucs
      2. Transcription (SynthTab | basic-pitch, avec fallback)
      3. Tuning detection
      4. Key detection
      5. Chord detection (BTC | legacy, avec fallback)
      6. Fretboard mapping
      7. Tab rendering (guitar, bass, vocals, drums, keys)
      8. [optionnel] Lyrics alignment (stable-whisper)
  → GET /api/jobs/{id}/results → JSON
  → Frontend : tab switcher étendu (Guitar · Bass · Vocals · Drums · Keys · Lyrics)
```

---

## 4. Error Handling

| Scénario | Comportement |
|----------|-------------|
| BTC model absent / OOM | Fallback legacy, `step_label` inclut "[fallback: legacy chord detection]" |
| SynthTab unavailable | Fallback basic-pitch, même pattern |
| stable-whisper timeout / OOM | Job `done` sans clé `lyrics` dans `tabs` ; frontend masque l'onglet |
| Findings critiques audit | Bloquent le sprint 1 — rien commité avant fix |

---

## 5. Testing Strategy

| Niveau | Quoi |
|--------|------|
| Unit | Mocks ML — `test_chord_detection_btc.py`, `test_transcription_synthtab.py` |
| Integration | Pipeline end-to-end sur un WAV synthétique court (< 10 s) |
| Benchmark | Dataset 5-10 WAV connus, script `benchmark.py` comparant legacy vs BTC/SynthTab |
| Smoke | Post-deploy : upload d'un WAV de 30 s sur `api.notara.app`, vérifier résultats |

---

## 6. Out of Scope

- App native Mac/iOS (spec séparé : `2026-07-17-mac-ios-tab-app-design.md`)
- Système de compte / persistance longue durée
- Monétisation
- Support de métriques 3/4, 5/4, 6/8 (backlog pipeline)

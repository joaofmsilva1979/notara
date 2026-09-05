# Sprint 0 — Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run all available audit tools on Notara, classify findings, and fix all critical issues before any code changes land.

**Architecture:** Read-only analysis phase — no feature code written here. Output is a findings document that gates Sprint 1+2.

**Tech Stack:** claude-security plugin, sharp-edges plugin, semgrep, codebase-audit-suite.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `docs/audit/2026-09-05-findings.md` | Create | All findings classified critical/major/minor |

---

### Task 1: Security scan with claude-security

**Files:**
- Create: `docs/audit/2026-09-05-findings.md`

- [ ] **Step 1: Run claude-security scan**

From Claude Code, invoke:
```
/security-audit
```
Or use the Agent tool with `claude-security:claude-security`. Point it at the repo root. Ask it to focus on:
- File upload handling (`api/routes.py` lines 76-88 — suffix check, size check, BytesIO)
- CORS policy (`api/main.py` — `allow_origins=["*"]`)
- Rate limiting (`api/routes.py` — `@limiter.limit("10/hour")`)
- YouTube URL validation (`api/routes.py` — `YT_PATTERN` regex)
- `subprocess.run` usage in `api/worker.py` lines 71-81
- Temp directory lifecycle and cleanup

- [ ] **Step 2: Run sharp-edges audit**

From Claude Code, invoke:
```
/sharp-edges
```
Focus areas: `api/worker.py` (subprocess with user-controlled URL), `api/routes.py` (file upload), `pipeline/chord_detection_btc.py` (torch.load with `weights_only=False`).

- [ ] **Step 3: Run semgrep static analysis**

From Claude Code, invoke:
```
/semgrep
```
Or use Agent with `static-analysis:semgrep-scanner`. Run on Python files. Pay attention to:
- Injection patterns in subprocess calls
- Path traversal in file writes
- Exception swallowing

- [ ] **Step 4: Classify findings and write report**

Create `docs/audit/2026-09-05-findings.md` with this structure:

```markdown
# Notara Security Audit — 2026-09-05

## CRITICAL (block Sprint 1 commit)
<!-- Issues that could allow RCE, data exfiltration, or service abuse -->

## MAJOR (fix in Sprint 1)
<!-- Issues with meaningful risk but no immediate exploit vector -->

## MINOR (backlog)
<!-- Code quality, defence-in-depth, non-exploitable issues -->
```

- [ ] **Step 5: Fix all CRITICAL findings before proceeding**

For each CRITICAL finding:
- Implement the fix
- Run `pytest` to confirm nothing breaks
- Commit: `git commit -m "fix: [finding description] (audit sprint 0)"`

- [ ] **Step 6: Confirm gate passed**

Run:
```bash
cd ~/Library/CloudStorage/GoogleDrive-davisthe8th@gmail.com/My\ Drive/GARAGEBAND/VALLETOFNOONE/guitar_tab_pipeline
.venv/bin/python3 -m pytest -q
```
Expected: all tests pass. No CRITICAL findings outstanding. Proceed to Sprint 1+2.

# AI Factory Template

Ein wiederverwendbares Gerüst für autonomes Vibecoding. Beschreibe dein Projektziel, befülle `specs/` und `tasks/` — und lass die KI-Agenten die Umsetzung übernehmen.

## Wie es funktioniert

```
Du beschreibst dein Ziel
    → specs/ ausfüllen (product_spec.md + architecture.md)
    → tasks/ befüllen (nummerierte .md Dateien)
    → Orchestrator starten
        → Claude Code implementiert jede Task
        → Reviewer prüft & committet automatisch
    → reports/session-report.md ansehen
```

## Architektur

| Rolle | Provider | Auth |
|---|---|---|
| Lead Architect | Gemini API | `GEMINI_API_KEY` |
| Critic | OpenAI API | `OPENAI_API_KEY` |
| Primary Builder | Claude Code CLI | `claude login` (Claude.ai / Claude Pro) |
| Fallback Builder | Codex CLI | `codex auth login` (ChatGPT Pro) oder `OPENAI_API_KEY` |
| Reviewer | Gemini API | `GEMINI_API_KEY` |

**API-key basiert:** Gemini und OpenAI Critic benötigen einen API-Key in `.env`.  
**Login-basiert:** Claude Code und Codex CLI werden einmalig interaktiv authentifiziert — kein API-Key nötig.

## Setup für ein neues Projekt

### 1. Template verwenden

```bash
# Option A: GitHub Template (wenn du es hochgeladen hast)
gh repo create mein-projekt --template dein-user/AI-Factory-Template

# Option B: Manuell kopieren
cp -r AI-Factory-Template mein-neues-projekt
cd mein-neues-projekt
git init && git add . && git commit -m "init: from AI Factory Template"
```

### 2. Projekt beschreiben

Bearbeite diese beiden Dateien **bevor** du den Orchestrator startest:

**`specs/product_spec.md`** — Was willst du bauen?
- Produktvision in natürlicher Sprache
- Wer sind die Nutzer?
- Welche Features braucht das MVP?

**`specs/architecture.md`** — Wie soll es gebaut werden?
- Tech Stack (Framework, Sprache, Datenbank)
- Verzeichnisstruktur
- Wichtige Architekturentscheidungen

### 3. Tasks anlegen

Erstelle nummerierte Markdown-Dateien in `/tasks/`:

```
tasks/
  01_project_setup.md
  02_database_schema.md
  03_main_feature.md
  ...
```

Jede Task-Datei beschreibt: **Was** soll gebaut werden (Requirements), **Deliverables** und **Verification**.

### 4. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
# Trage ein: GEMINI_API_KEY und OPENAI_API_KEY
```

### 5. Geteilte Auth-Volumes einmalig erstellen

Diese Volumes werden **einmalig pro Docker-Host** erstellt – nicht pro Projekt.
Sie speichern die Claude Code und Codex CLI Authentifizierung global,
sodass du dich bei neuen Projekten nicht erneut anmelden musst.

```bash
docker volume create claude_auth
docker volume create codex_auth
```

> Dieser Schritt ist nur beim allerersten Mal nötig. Bei weiteren Projekten
> aus diesem Template sind die Volumes bereits vorhanden und die Anmeldung
> bleibt erhalten.

### 6. Docker Container starten

```bash
docker-compose up -d
```

> Beim ersten Start wird der Container gebaut (~2-3 Minuten). Claude Code und Codex CLI werden automatisch installiert.

### 7. Builder-Authentifizierung einrichten

Einmalig nach dem ersten Container-Start:

```bash
# Claude Code (Primary Builder) — Claude.ai / Claude Pro Login
docker exec -it ai-factory-dev claude login

# Codex CLI (Fallback Builder) — nur nötig wenn CODEX_ENABLED=true
docker exec -it ai-factory-dev codex auth login
# Alternativ: OPENAI_API_KEY in .env setzen
```

### 8. Orchestrator ausführen

```bash
# Alle offenen Tasks automatisch abarbeiten:
docker exec -it ai-factory-dev python run_graph.py

# Eine einzelne Task manuell starten:
docker exec -it ai-factory-dev python run_graph.py --task tasks/01_project_setup.md
```

### 9. Ergebnisse prüfen

- **`reports/session-report.md`** — Was wurde gebaut, welche Dateien geändert, offene Punkte
- **Git History** — Jede Task = 1 Commit, vollständige Nachvollziehbarkeit
- **`app/`** — Der generierte App-Code

## Projektstruktur

```
AI-Factory-Template/
├── orchestrator/               # LangGraph Agenten-Orchestrator
│   ├── graph.py                # State Machine: preflight → build → review → report
│   ├── state.py                # Geteilter State zwischen den Nodes
│   ├── llm/
│   │   ├── roles.py            # Rolle → Provider → Modell Mapping
│   │   └── providers.py        # Gemini & OpenAI SDK Wrapper
│   └── nodes/
│       ├── preflight_environment.py   # Prüft Tools & Dateien
│       ├── build_with_claude.py       # Claude Code CLI als Primary Builder
│       ├── fallback_build_with_codex.py  # Codex CLI als Fallback Builder
│       ├── review_with_gemini.py      # Gemini Code Review
│       ├── review_and_commit.py       # Git add + commit
│       └── report_done.py             # Gibt Zusammenfassung aus
├── .agent/
│   └── AGENTS.md              # Regeln für den Coding Agent
├── specs/                     # ← DEIN PROJEKT: Produkt & Architektur
│   ├── product_spec.md        # Was baust du?
│   └── architecture.md        # Wie baust du es?
├── tasks/                     # ← DEIN PROJEKT: nummerierte Task-Dateien
├── reports/                   # Automatisch generierte Session-Reports
├── app/                       # Automatisch generierter App-Code
├── Dockerfile                 # Python 3.11 + Node + Claude Code + Codex + Git
├── docker-compose.yml         # Container-Setup
├── entrypoint.sh              # Setzt Permissions & Git-Config beim Start
└── run_graph.py               # Einstiegspunkt für den Orchestrator
```

## Konfiguration

### Umgebungsvariablen

| Variable | Default | Beschreibung |
|---|---|---|
| `GEMINI_API_KEY` | — | Pflicht: Architect & Reviewer |
| `OPENAI_API_KEY` | — | Pflicht: Critic; optional: Codex fallback auth |
| `GEMINI_ARCHITECT_MODEL` | `gemini-2.5-pro` | Modell für Architect |
| `GEMINI_REVIEW_MODEL` | `gemini-2.5-pro` | Modell für Reviewer |
| `OPENAI_CRITIC_MODEL` | `gpt-5.4-mini` | Modell für Critic |
| `CODEX_ENABLED` | `false` | Codex CLI Fallback aktivieren |
| `CLAUDE_TIMEOUT` | `600` | Timeout für Claude Code CLI (Sekunden) |
| `CODEX_TIMEOUT` | `300` | Timeout für Codex CLI (Sekunden) |
| `VALIDATION_COMMAND` | — | Test-Befehl vor Commit (z.B. `pytest tests/`) |
| `MAX_TASK_RETRIES` | `2` | Max Wiederholungen pro Task |
| `PROJECT_ROOT` | `/workspace` | Pfad zum Projektverzeichnis im Container |

### Lifecycle- und Git-Regeln

- Builder dürfen keine Commits erzeugen; der Orchestrator bricht ab, wenn sich `HEAD` während eines Builder-Laufs ändert.
- Eine Task wird erst nach Review-Freigabe und erfolgreicher Validation in `.done.md` umbenannt.
- Die `.done.md`-Markierung wird im selben Commit wie die Task-Änderungen gespeichert.
- Der Reviewer bewertet nur Änderungen seit der vor dem Task erfassten Workspace-Baseline.
- Offene Rückfragen stoppen die Planung; beantwortete Fragen werden beim nächsten Planungsdurchlauf berücksichtigt.

### Tasks als "erledigt" markieren

Benenne eine Task-Datei um und füge `.done.` ein — sie wird dann übersprungen:

```
tasks/01_project_setup.done.md   ← wird übersprungen
tasks/02_database_schema.md      ← wird ausgeführt
```

## Voraussetzungen

- Docker Desktop (Windows/Mac) oder Docker Engine (Linux)
- Git
- Gemini API Key
- OpenAI API Key
- Claude.ai / Claude Pro Account (für Claude Code Login)
- Optional: ChatGPT Pro Account (für Codex Fallback Login)

## FAQ

**Q: Was passiert wenn Claude scheitert?**  
A: Der Orchestrator versucht automatisch Codex CLI als Fallback (wenn `CODEX_ENABLED=true`). Scheitert auch Codex, wird ein Fehlerbericht erstellt.

**Q: Brauche ich einen Anthropic API Key?**  
A: Nein. Claude Code authentifiziert sich via `claude login` (Claude.ai / Claude Pro Account). Kein API-Key nötig.

**Q: Kann ich mehrere Projekte parallel betreiben?**  
A: Ja — einfach das Template mehrfach klonen. Jedes Projekt ist ein eigenständiger Container mit eigenem `/workspace`. Die Claude Code und Codex CLI Authentifizierung wird automatisch über alle Projekte geteilt (via `claude_auth`- und `codex_auth`-Volumes).

**Q: Wo finde ich den vollständigen Verlauf der Änderungen?**  
A: In der Git-History (`git log`) und in `reports/session-report.md`.

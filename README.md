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

### 4. Docker Container starten

```bash
docker-compose up -d
```

> Beim ersten Start wird der Container gebaut (~2-3 Minuten). Claude Code wird automatisch installiert.

### 5. Orchestrator ausführen

```bash
# Alle offenen Tasks automatisch abarbeiten:
docker exec -it ai-factory-dev python run_graph.py

# Eine einzelne Task manuell starten:
docker exec -it ai-factory-dev python run_graph.py --task tasks/01_project_setup.md
```

### 6. Ergebnisse prüfen

- **`reports/session-report.md`** — Was wurde gebaut, welche Dateien geändert, offene Punkte
- **Git History** — Jede Task = 1 Commit, vollständige Nachvollziehbarkeit
- **`app/`** — Der generierte App-Code

## Projektstruktur

```
AI-Factory-Template/
├── orchestrator/               # LangGraph Agenten-Orchestrator
│   ├── graph.py                # State Machine: preflight → build → review → report
│   ├── state.py                # Geteilter State zwischen den Nodes
│   └── nodes/
│       ├── preflight_environment.py   # Prüft Tools & Dateien
│       ├── build_with_claude.py       # Claude Code als Coding Agent
│       ├── fallback_build_with_codex.py  # Fallback falls Claude scheitert
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
├── Dockerfile                 # Python 3.11 + Node + Claude Code + Git
├── docker-compose.yml         # Container-Setup
├── entrypoint.sh              # Setzt Permissions & Git-Config beim Start
└── run_graph.py               # Einstiegspunkt für den Orchestrator
```

## Konfiguration

### Umgebungsvariablen

| Variable | Default | Beschreibung |
|---|---|---|
| `PROJECT_ROOT` | `/workspace` | Pfad zum Projektverzeichnis im Container |
| `ANTHROPIC_API_KEY` | — | Für Claude API (falls benötigt) |

### Tasks als "erledigt" markieren

Benenne eine Task-Datei um und füge `.done.` ein — sie wird dann übersprungen:

```
tasks/01_project_setup.done.md   ← wird übersprungen
tasks/02_database_schema.md      ← wird ausgeführt
```

## Voraussetzungen

- Docker Desktop (Windows/Mac) oder Docker Engine (Linux)
- Git
- Anthropic API Key (für Claude Code)

## FAQ

**Q: Was passiert wenn Claude scheitert?**  
A: Der Orchestrator versucht automatisch Codex als Fallback. Scheitert auch Codex, wird ein Fehlerbericht erstellt.

**Q: Kann ich mehrere Projekte parallel betreiben?**  
A: Ja — einfach das Template mehrfach klonen. Jedes Projekt ist ein eigenständiger Container.

**Q: Wo finde ich den vollständigen Verlauf der Änderungen?**  
A: In der Git-History (`git log`) und in `reports/session-report.md`.

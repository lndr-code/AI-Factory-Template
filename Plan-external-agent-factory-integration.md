# ADR-002 — Anbindung der AI Factory als externe Coding-Agentur

**Status:** Entwurf — wartet auf menschliche Freigabe
**Datum:** 2026-05-07
**Bezug:** [AGENTS.md](../../AGENTS.md), [CLAUDE.md](../../CLAUDE.md),
[docs/architecture/current_mvp.md](../architecture/current_mvp.md),
[ADR-001 GitHub Workflow](ADR-001-github-workflow.md)
**Externer Bezug:** `lndr-code/AI-Factory-Template` (separates Repository)

**Arbeitsnotiz:** Dieses Dokument ist das Arbeitsdokument für External Mode v0 im AI-Factory-Template.

---

## 1. Kontext

Es liegen zwei Vorarbeiten vor:

1. ein **Deep Research** über `lndr-code/AI-Factory-Template` und `lndr-code/idp_pipeline`,
   das einen "External-Agency-Modus" der Factory entwirft, mit dem das IDP-Repo
   bearbeitet werden soll;
2. ein **ChatGPT-Review** dieses Plans, das das Zielbild bestätigt, aber für
   die Umsetzung ein konservatives Stufenmodell `v0 → v1 → v2 → v3`
   vorschlägt.

Diese ADR fasst beide Vorarbeiten zusammen, prüft sie gegen den realen
Code-Stand beider Repos und definiert die verbindlichen Leitplanken für die
Anbindung. Die Umsetzung selbst geschieht im AI-Factory-Repo, nicht hier;
diese Datei dokumentiert nur, **was die Factory am IDP-Repo darf**.

## 2. Verifikationsbefunde

### 2.1 IDP-Repo (verifiziert lokal, Stand 2026-05-07)

| Behauptung | Befund |
| --- | --- |
| `pytest tests/test_smoke.py -v` als Smoke-Test | bestätigt; `tests/test_smoke.py` setzt Dummy-Env vor Import |
| CI auf push `develop`/`feature/**`/`fix/**`/`chore/**`/`test/**` | bestätigt in `.github/workflows/smoke.yml` |
| `requirements-ci.txt` für CI ohne PaddleOCR | bestätigt; `requirements-dev.txt` referenziert `requirements-ci.txt` |
| Devcontainer enthält Tesseract, aber **keine** Builder-CLIs | bestätigt; `.devcontainer/Dockerfile` installiert nur `git`, `tesseract-ocr`, `tesseract-ocr-deu` |
| `IDP_Architekturplan.md` ist vertraulich | bestätigt in `.dockerignore`, **aber nicht in `.gitignore`** — Datei ist im privaten Repo committed; Agents dürfen lesen, nicht in öffentliche Logs schreiben |
| AGENTS.md erlaubt direkten `develop`-Commit für kleine Aufgaben | bestätigt in `AGENTS.md` Branch-Workflow-Tabelle |
| `.env`, `data/`, `output/`, `input_pdfs/`, `archive/`, `Testdaten/`, `logs/` in `.gitignore` | bestätigt |

### 2.2 AI-Factory-Repo (verifiziert via `git clone`, Stand 2026-05-07)

| Behauptung im Deep Research | Befund |
| --- | --- |
| `PROJECT_ROOT` ist Modul-Konstante, default `os.getcwd()` | bestätigt in `run_graph.py` und `orchestrator/git_utils.py` |
| Tasks werden in `PROJECT_ROOT/tasks/` gesucht | bestätigt; `find_open_tasks()` und `check_tasks_exist` |
| Builder schreibt Report in `PROJECT_ROOT/reports/session-report.md` | bestätigt in `build_with_claude.py` und `fallback_build_with_codex.py` |
| Commit-Knoten benennt Task-Datei zu `.done.md` um | bestätigt in `review_and_commit.py` (`_done_task_path`) |
| Commit-Message ist hartkodiert `feat:` | bestätigt: `f"feat: complete {task_name} [automated]"` |
| `_SYSTEM_PROTECTED` enthält `Dockerfile`, `requirements.txt`, `orchestrator/`, `run_graph.py`, `docker-compose.yml`, `.agent/` | bestätigt in `review_with_gemini.py` |
| `docker-compose.yml` mountet aktuelles Verzeichnis als `/workspace` | bestätigt |
| `VALIDATION_COMMAND` als Pre-Commit-Schranke vorhanden | bestätigt in `review_and_commit.py:_run_validation` |
| HEAD-Guard verhindert Builder-Commits | bestätigt: `assert_head_unchanged` und Vergleich `head_before` vs. `head_after` |
| Codex-CLI wird mit `--approval-mode full-auto` aufgerufen | bestätigt — laut Deep Research veraltete Syntax (aktuell: `--full-auto`) |
| Auth-Volumes `claude_auth`/`codex_auth` werden global geteilt | bestätigt im `docker-compose.yml` |

### 2.3 Drei zusätzliche Befunde, die im Deep Research und ChatGPT-Review fehlen

Diese sind für den External-Mode entscheidend und werden in der finalen
Spezifikation unten korrekt eingeplant:

1. **Architect-/Critic-Phase ist nicht erwähnt.** Das Template hat einen
   `architect_agent → critic_agent → architect_refine`-Flow, der ausgelöst
   wird, sobald `tasks/` leer ist. Im External-Mode muss dieser Flow
   **explizit deaktivierbar** sein, sonst beginnt die Factory beim ersten
   Lauf, eigene Specs für das IDP-Repo zu generieren — was der Pflichtlektüre
   widerspricht.
2. **`_SYSTEM_PROTECTED` ist Template-zentriert.** `Dockerfile`,
   `requirements.txt`, `orchestrator/` etc. sind im IDP-Kontext entweder
   irrelevant (kein `orchestrator/`) oder genau die Dateien, die ein Agent
   legitim ändern darf (z.B. `requirements.txt` für Dev-Dependencies). Die
   Schutzliste muss daher pro Target aus dem Manifest kommen, nicht aus dem
   Reviewer-Code.
3. **`git_utils.PROJECT_ROOT` ist Modulkonstante.** Eine saubere
   FACTORY_ROOT/TARGET_ROOT-Trennung ist mit der aktuellen Architektur nur
   durch Setzen der Umgebungsvariable **vor** dem Python-Import möglich oder
   durch Refactoring der Git-Helfer auf einen explizit übergebenen
   `repo_root`. Für v0 reicht der Env-Variable-Ansatz, für v2+ wird der
   Refactor empfohlen.

## 3. Bewertung der beiden Vorarbeiten

### 3.1 Deep Research

**Stark:** Dual-Root-Modell, Pflichtlektüre-Gate mit Hash-Digests,
Trennung der Eingangskanäle (Factory-Task vs. GitHub-Issue), saubere
Branch-Präfix-Konvention, korrekte Identifikation der Wiederverwendungs-
fähigen Bausteine (Preflight/Build/Review/Commit, HEAD-Guard, Validation-
Schranke), korrekte Identifikation der nicht wiederverwendbaren Annahmen
(`specs/tasks/questions/reports` im selben Workspace, hartkodierte
Schutzliste, `feat:`-Default).

**Schwach:** Der Plan vermischt v0-Kandidaten und Endzustand stellenweise
(z.B. Sparse-Checkout, Issue-Adapter, Devcontainer-Validierung als ob alles
im selben Schritt zu bauen wäre). Die Architect-Phase wird nicht behandelt.
Codex-CLI-Versionierung wird zwar erwähnt, aber nicht als Hard Requirement
ausgewiesen — der aktuelle Template-Code ruft `codex --approval-mode
full-auto` auf, das je nach installierter Codex-Version bricht.

### 3.2 ChatGPT-Review

**Stark:** Stufenmodell `v0 → v1 → v2 → v3`, harte Position "Factory pusht
nie auf `develop`, nur Agent-Branches" (für eine Automation strenger und
sicherer als die menschen-orientierte AGENTS.md-Regel), pragmatische
Reduktion (Sparse-Checkout später, Issue-Adapter später, redigierte Logs
schon ab v1), klare Trennung "muss sofort" vs. "kann später" bei Sicherheit.

**Schwach:** Der Vorschlag "Factory darf in v0 nur lokal committen" ist
in der Konsequenz unscharf — ein lokaler Commit, der nie gepusht wird,
ist für eine Automation effektiv ein No-Op und schwer auditierbar.
Sauberer ist: v0 erzeugt **gar keinen** Commit, sondern einen
**Patch-/Diff-Artefakt** im FACTORY_ROOT, das ein Mensch reviewt.
Diese Korrektur übernimmt diese ADR (siehe v0 unten).

## 4. Eigene Optimierungen gegenüber beiden Vorarbeiten

1. **Kein Commit in v0, sondern Patch-Artefakt.** Der Builder-Diff wird
   nach grünem Smoke-Test in `FACTORY_ROOT/runs/<run_id>/changes.patch`
   abgelegt, nicht ins Zielrepo gecommittet. Erst v1 erzeugt einen
   Commit auf einem Agent-Branch und pusht.
2. **Architect-/Critic-Phase im External-Mode hart abschaltbar.** Das
   Manifest enthält `planning.architect_phase: disabled`. `run_graph.py`
   im External-Mode darf `check_tasks_exist` so überbrücken, dass es nie
   in `architect_agent` routet, sondern bei "no tasks" sauber endet.
3. **`_SYSTEM_PROTECTED` aus dem Manifest beziehen.** Im External-Mode
   gilt nicht die Template-eigene Schutzliste, sondern eine pro Zielprojekt
   konfigurierte Liste, abgeleitet aus den Deny-Globs des Manifests plus
   einer Whitelist legitimer Änderungspfade.
4. **Commit-Typ ableiten, nicht hartkodieren.** Bereits in v1 wird der
   Commit-Präfix (`feat`/`fix`/`chore`/`test`/`docs`) aus einem Pflichtfeld
   in der Task-Datei gelesen, nicht aus `feat: complete` zusammengebaut.
5. **Codex-CLI versionieren und als wählbaren Builder aktivieren.** Der
   alte Template-Adapter mit `--approval-mode full-auto` bleibt für den
   In-Repo-Modus unberührt, aber der External-Mode nutzt ab Durchlauf 3
   den modernen nicht-interaktiven Pfad `codex exec` mit
   `--sandbox workspace-write`, `--ask-for-approval never`, `--cd
   TARGET_ROOT` und `--add-dir RUN_DIR`. Damit kann Codex die
   Claude-Session-Limits abfedern, ohne den External-Mode mit
   `danger-full-access` zu öffnen.
6. **Pflichtlektüre nicht nur lesen, sondern als Prompt-Block einspeisen.**
   Der Builder-Prompt im External-Mode ersetzt den `/specs/`-Verweis durch:
   "Lies und befolge zwingend `CLAUDE.md`, `AGENTS.md`,
   `docs/architecture/current_mvp.md`. Setze die Read-Receipt erst nach
   Bestätigung." Plus: die SHA256 jeder dieser Dateien wird im Prompt
   explizit angegeben, damit der Builder die korrekte Version verifizieren
   kann.
7. **Reports nie ins Zielrepo, redigierte Logs schon ab v0.** Bereits in
   v0 werden Builder-`stdout`/`stderr` nicht im State persistiert, sondern
   in einen lokalen Run-Ordner geschrieben und beim Übergang in den finalen
   Report auf Datei-Listen, Exit-Codes und kurze Fehlerauszüge reduziert.
   Das ist günstiger als später nachzurüsten.

## 5. Zielarchitektur (kompakt)

```
┌──────────────────────────────────────────────────────────────────┐
│                          AI FACTORY HOST                          │
│                                                                   │
│   FACTORY_ROOT (= AI-Factory-Repo, Code & Run-Artefakte)          │
│   ├── orchestrator/        (LangGraph Flow, unverändert)          │
│   ├── targets/                                                    │
│   │   └── idp_pipeline.yaml   ← Manifest pro Zielprojekt          │
│   ├── factory_tasks/                                              │
│   │   └── idp_pipeline/                                           │
│   │       └── 001_<task>.md   ← Aufgaben für IDP, getrennt        │
│   └── runs/                                                       │
│       └── <run_id>/                                               │
│           ├── read_receipt.json   (Hashes der Pflichtdokumente)   │
│           ├── changes.patch       (v0: Diff statt Commit)         │
│           ├── validation.log                                      │
│           └── report.md           (redigiert)                     │
│                                                                   │
│   TARGET_ROOT (= geklonte Arbeitskopie idp_pipeline)              │
│   └── … (bleibt frei von Factory-Artefakten)                      │
└──────────────────────────────────────────────────────────────────┘
```

Pro Lauf: Factory klont (oder öffnet) das IDP-Repo in TARGET_ROOT, checkt
`develop` aus, lädt die Pflichtlektüre, ruft den Builder mit gesetztem
Working Directory auf TARGET_ROOT auf, sammelt den Diff, validiert,
schreibt das Run-Artefakt zurück nach FACTORY_ROOT.

## 6. Stufenmodell

### v0 — Schmaler Pfad, kein Push, kein Commit ins Zielrepo

**Ziel:** Eine Factory-seitige Task-Datei kann das IDP-Repo extern
bearbeiten und liefert einen Patch zurück. Mensch reviewt und committet.

**In v0 enthalten:**

- `targets/idp_pipeline.yaml` mit Repo-URL, `base_branch: develop`,
  `protected_branches: [main]`, Pflichtlektüre, `validation_command:
  pytest tests/test_smoke.py -v`, Deny-Globs (siehe §7), `builders.primary:
  claude`, `builders.fallback: null`, `planning.architect_phase: disabled`.
- Trennung `FACTORY_ROOT` und `TARGET_ROOT` per Umgebungsvariable;
  `PROJECT_ROOT` für die Git-Helfer wird pro Lauf auf `TARGET_ROOT` gesetzt.
- Open-Target-Schritt: vorhandenes TARGET_ROOT öffnen oder frisch klonen,
  `develop` auschecken, Sauberkeit prüfen, Deny-Globs verifizieren.
- Pflichtlektüre-Gate: `CLAUDE.md`, `AGENTS.md`,
  `docs/architecture/current_mvp.md` lesen, SHA256 berechnen, in
  `read_receipt.json` ablegen. Hashes gehen als Kontext in den
  Builder-Prompt; Lauf bricht ab, wenn eine Datei während des Laufs
  ihren Hash ändert.
- Builder-Aufruf (Claude Code) im TARGET_ROOT, Working Directory ist
  TARGET_ROOT. Builder darf nicht committen (HEAD-Guard wie heute).
- Validation: `pytest tests/test_smoke.py -v` im TARGET_ROOT.
- Bei Erfolg: `git diff` als `changes.patch` in
  `FACTORY_ROOT/runs/<run_id>/`. Bei Fehler: kurze redigierte
  Fehlernotiz, ebenfalls dort.
- Report (redigiert) in FACTORY_ROOT, **nie** in `reports/` des IDP-Repos.

**Nicht in v0:**

- Kein Commit, kein Push, kein PR, kein Merge.
- Keine GitHub-Issue-Integration.
- Keine Devcontainer-basierte Validation (lokale `pytest`-Ausführung).
- Kein Sparse-Checkout, kein gefilterter Workspace.
- Codex ist ab Durchlauf 3 als wählbarer External Builder erlaubt; der
  alte In-Repo-Codex-Adapter bleibt davon getrennt.
- Keine Read-Receipt-Verifikation als Hash-Echo durch den Builder
  (kommt in v1).

**Akzeptanzkriterien v0** (alle müssen erfüllt sein):

| ID | Kriterium |
| --- | --- |
| A0.1 | Manifest `targets/idp_pipeline.yaml` existiert und ist gültiges YAML |
| A0.2 | Lauf gegen einen sauberen `develop`-Stand erzeugt einen Patch in `FACTORY_ROOT/runs/<run_id>/changes.patch`, der manuell mit `git apply --check` im IDP-Repo ohne Konflikt durchläuft |
| A0.3 | Lauf erzeugt **keinerlei** Dateien in `IDP_Pipeline_V2/reports/`, `tasks/`, `specs/`, `questions/` |
| A0.4 | `pytest tests/test_smoke.py -v` läuft im TARGET_ROOT vor Patch-Erstellung grün |
| A0.5 | Lauf bricht sauber ab, wenn vorab eine der Pflichtdateien fehlt oder ihr Hash sich während des Laufs ändert |
| A0.6 | Lauf bricht sauber ab, wenn TARGET_ROOT eine Datei aus den Deny-Globs enthält (z.B. `.env`, `data/`) |
| A0.7 | `read_receipt.json` enthält SHA256 für `CLAUDE.md`, `AGENTS.md`, `docs/architecture/current_mvp.md` |
| A0.8 | Builder-Versuch, einen Commit zu erzeugen, schlägt durch HEAD-Guard fehl und führt zu `policy_violation`-Status (verifiziert mit synthetischem Test-Task, der `git commit` provoziert) |
| A0.9 | `_SYSTEM_PROTECTED` aus Reviewer ist im External-Mode aus dem Manifest geladen, nicht aus `review_with_gemini.py` hartkodiert |
| A0.10 | Bestehender In-Repo-Modus der Factory funktioniert weiterhin gegen ein anderes Test-Repo (Regression) |

### v1 — Agent-Branch und Push

**Neu in v1:**

- Lauf erstellt im TARGET_ROOT einen temporären Branch
  `feature/agent-<task-id>` (oder `fix/`/`chore/`/`test/`/`docs/` je
  nach Task-Typ).
- Commit mit aus Task abgeleitetem Präfix (kein hartkodiertes `feat:`).
- Push des Branches nach `origin`.
- **Kein** automatisches Öffnen eines Pull Requests; das bleibt
  bewusst Mensch-getrieben.
- Read-Receipt-Hash-Echo: der Builder muss in seinem Output die SHA256
  der drei Pflichtdokumente nennen, sonst wird der Lauf verworfen.
- Logs werden bereits ab v1 auf Datei-Listen, Exit-Codes und kurze
  Fehlerauszüge reduziert; vollständige Builder-`stdout`/`stderr`
  bleiben höchstens 24 h im FACTORY_ROOT-Run-Ordner und werden danach
  gelöscht.

**Nicht in v1:**

- Keine PR-Erstellung, keine Issue-Sync.
- Keine Merge-Operationen jeglicher Art.
- Niemals auf `develop` committen — Agent-Branch ist Pflicht.

### v2 — GitHub-Issue-Eingang und Draft-PR

**Neu in v2:**

- Issue-Adapter: zieht Issue-Body und maßgebliche Maintainer-Kommentare,
  materialisiert daraus eine Factory-seitige Normalform-Task. Akzeptiert
  `agent-ready`-Label als Trigger.
- Reviewer-Agent kommentiert den entstehenden Draft-PR mit kurzer
  Zusammenfassung der Änderungen, der bestandenen Validation und der
  bekannten Risiken — explizit als `Draft`, nie als ready-for-review.
- Devcontainer-Validation als optionaler Schalter
  (`validation.mode: devcontainer`): `devcontainer up` auf TARGET_ROOT
  und `pytest tests/test_smoke.py -v` darin.
- Mehrere parallele Worktrees pro Zielprojekt (`git worktree`) für
  unabhängige Tasks.

**Nicht in v2:**

- Kein automatischer Merge (`develop` ← Agent-Branch oder `main` ←
  `develop`) — bleibt menschliche Entscheidung.

### v3 — Sparse-Checkout, Policy-Diff-Gates, Multi-Target

**Neu in v3:**

- Sparse-Checkout / gefilterter Workspace: TARGET_ROOT enthält physisch
  nur die erlaubten Pfade. Reduziert die Angriffsfläche bei Codex und
  Builder-Fehlverhalten erheblich.
- Policy-Diff-Gates: jede Änderung an `AGENTS.md`, `CLAUDE.md`,
  `docs/architecture/current_mvp.md`, `.github/workflows/*.yml`,
  `.devcontainer/**` durch einen Agenten erfordert eine ADR im selben
  Patch und friert den Lauf andernfalls ein.
- Mehrere Zielprojekte parallel im selben Factory-Host, mit pro-Target-
  Auth-Profilen.
- Auditierte Agentenläufe: Run-State, Patches und Validation-Logs werden
  signiert in einem schreibgeschützten Archiv abgelegt
  (Behörden-Audit-Tauglichkeit).

## 7. Manifest für `targets/idp_pipeline.yaml`

```yaml
# AI-Factory-Manifest für lndr-code/idp_pipeline
# Diese Datei lebt im AI-Factory-Repo, NICHT im IDP-Repo.

repo: git@github.com:lndr-code/idp_pipeline.git
base_branch: develop
protected_branches:
  - main

required_read_files:
  - CLAUDE.md
  - AGENTS.md
  - docs/architecture/current_mvp.md

planning:
  architect_phase: disabled        # External-Mode: niemals Specs generieren

task_sources:
  - factory_task_file              # v0: nur Factory-seitige Markdown-Tasks
  # - github_issue                 # ab v2

validation:
  command: pytest tests/test_smoke.py -v
  mode: local                       # ab v2: optional "devcontainer"
  timeout_seconds: 300

builders:
  primary: codex                    # v0 Durchlauf 3: Codex ist First-Class Builder
  fallback: claude                  # optionaler manueller Ausweich-Builder

commit:
  enabled_from_version: v1          # v0: kein Commit, nur Patch-Artefakt
  branch_strategy: agent_branch     # nie direkt auf develop
  branch_prefixes:
    - feature/agent-
    - fix/agent-
    - chore/agent-
    - test/agent-
    - docs/agent-
  message_prefix_from_task: true    # feat/fix/chore/test/docs aus Task ableiten
  push_enabled_from_version: v1
  pr_enabled_from_version: v2

security:
  deny_globs:
    - .env
    - .env.*
    - data/**
    - input_pdfs/**
    - output/**
    - archive/**
    - Testdaten/**
    - logs/**
    - "**/*.pdf"
  abort_if_deny_glob_present: true
  protected_paths_in_diff:
    # Diff in diese Pfade führt zu Pflicht-ADR-Forderung (ab v3 auch hartem Stopp)
    - .github/workflows/**
    - .devcontainer/**
    - AGENTS.md
    - CLAUDE.md
    - docs/architecture/current_mvp.md
  log_redaction:
    drop_fields: [stdout, stderr]
    keep_fields: [exit_code, changed_files, duration_seconds, error_summary]
```

## 8. Konkrete Umsetzungsaufgaben für die AI Factory (v0)

Diese Liste gehört zwar in das Factory-Repo, wird aber hier dokumentiert,
damit klar ist, was am IDP-Repo erwartet wird. Auf Factory-Seite:

1. **Target-Manifest-Loader** (`orchestrator/external/manifest.py`):
   liest `targets/<name>.yaml`, validiert Schema, gibt `ExternalTargetConfig`
   zurück.
2. **Open-Target-Node** (`orchestrator/nodes/open_external_target.py`):
   ersetzt im External-Mode den Architect-Pfad. Klont oder öffnet das
   IDP-Repo unter TARGET_ROOT, checkt `base_branch` aus, prüft
   Sauberkeit, prüft Deny-Globs.
3. **Read-Receipt-Node** (`orchestrator/nodes/read_receipt.py`): liest
   Pflichtdokumente, schreibt SHA256-Map in `runs/<run_id>/read_receipt.json`,
   reicht die Hashes an den Builder-Prompt durch.
4. **PROJECT_ROOT-Bridge:** entweder per Env-Variable vor `import` der
   Factory oder Refactor von `orchestrator/git_utils.py` auf einen
   übergebenen `repo_root`. Für v0 reicht der Env-Ansatz.
5. **External-Builder-Prompt:** ersetzt im External-Mode den
   `/specs/`-Block durch IDP-Pflichtlektüre und Hash-Echo-Anforderung.
   Zielort der Implementierungs-Zusammenfassung wird auf
   `FACTORY_ROOT/runs/<run_id>/builder_summary.md` geleitet, **nicht** auf
   `TARGET_ROOT/reports/`.
6. **Reviewer-Schutzliste aus Manifest:** ersetzt das hartkodierte
   `_SYSTEM_PROTECTED` in `review_with_gemini.py` durch das, was im
   Manifest steht, wenn der External-Mode aktiv ist.
7. **Patch-statt-Commit-Pfad** (`orchestrator/nodes/external_finalize.py`):
   wenn `commit.enabled_from_version > v0`, lauf endet mit `git diff`
   als Patch-Datei und sauberem Reset des TARGET_ROOT-Workdirs. Kein
   `git add`, kein `git commit`, keine `.done.md`-Umbenennung im IDP-Repo.
8. **Regressionsschutz für In-Repo-Modus:** External-Mode ist über eine
   Umgebungsvariable oder ein CLI-Flag geschaltet; ohne Flag verhält
   sich die Factory wie heute.

Im IDP-Repo selbst ist für v0 **keine** Änderung nötig — diese ADR
dokumentiert nur den Vertrag.

## 9. Risiken und offene Fragen

| Risiko | Bewertung | Gegenmaßnahme |
| --- | --- | --- |
| Codex-Fallback führt zu Datenabfluss (Prompt-Kontext) | mittel | Codex bleibt v0–v2 aus, Aktivierung erst nach gefiltertem Workspace (v3) |
| Builder ändert `requirements.txt` ohne ADR | mittel | `requirements.txt` und `requirements-ci.txt` zu `protected_paths_in_diff` aufnehmen; Lauf erzeugt Pflicht-ADR-Hinweis im Patch |
| Geheimnisse aus `.env` gelangen in Logs | hoch | `.env` ist in Deny-Globs, Lauf bricht ab; Logs ab v0 redigiert |
| `IDP_Architekturplan.md` (vertraulich) wird im Patch zitiert | mittel | Datei zu `protected_paths_in_diff` aufnehmen; Builder-Prompt darf Inhalte lesen, aber nicht in Logs/Reports zurückspielen |
| Smoke-Test grün, aber semantische Regression | mittel | Bewusst akzeptiert in v0/v1; ab v2 Reviewer-Agent als zusätzliche Gate |
| AGENTS.md-Erlaubnis "kleine Änderung direkt auf `develop`" steht im Widerspruch zur Factory-Regel "nie direkt auf `develop`" | niedrig | Bewusste Verschärfung für Automation. AGENTS.md gilt für Menschen mit Urteilsvermögen, die Factory-Regel gilt für die Automation. Diese ADR dokumentiert die Verschärfung. |
| `git_utils.PROJECT_ROOT` als Modulkonstante macht Zwei-Repo-Betrieb fragil | mittel | Env-Variable-Ansatz für v0 dokumentiert, Refactor auf `repo_root`-Parameter in v2 geplant |

**Offene Frage 1:** Sollen wir den AGENTS.md-Branch-Workflow um eine
kurze Notiz erweitern, dass automatisierte Agents ausschließlich
Agent-Branches verwenden dürfen, auch für kleine Aufgaben? Empfehlung: ja,
in eigenem PR nach v0-Stabilisierung, **nicht** als Teil dieses ADR-Drafts.

**Offene Frage 2:** Soll die Factory ab v2 PR-Beschreibungen mit
Verweis auf diese ADR (ADR-002) erzeugen? Empfehlung: ja, plus
Verlinkung auf `read_receipt.json` des Laufs für volle Auditierbarkeit.

## 10. Entscheidung

Diese ADR legt das Zielbild und das Stufenmodell fest. Die Umsetzung
erfolgt **außerhalb** dieses Repos im AI-Factory-Repo, mit der unter §8
beschriebenen Aufgabenliste. Im IDP-Repo selbst sind für v0 keine
Änderungen erforderlich.

Freigabe-Status: Entwurf. Diese Datei wird auf einem Agent-Branch
ergänzt/korrigiert (nicht direkt auf `develop`), und ein Mensch
entscheidet über den Merge nach `develop` und später nach `main`.

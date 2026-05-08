# External Mode

External Mode erlaubt der AI Factory, in einem **externen Ziel-Repository** zu arbeiten, ohne dieses Repo in das Factory-Repo zu integrieren. Der Agent klont das Ziel-Repo lokal, implementiert eine Aufgabe, und liefert einen Patch zurück — kein direkter Commit, keine Push-Operation (in v0).

---

## Konzept

```
AI-Factory-Repo (Factory Root)
├── targets/my-project.yaml     ← Manifest für das Zielprojekt
├── factory_tasks/              ← Aufgaben-Dateien (lokal, nicht committed)
└── runs/                       ← Lauf-Artefakte: Patches, Reports (lokal)

external_targets/my-project/    ← geklontes Ziel-Repo (lokal, nicht committed)
```

Der Factory-Agent liest das Manifest, klont das Ziel-Repo (falls noch nicht vorhanden), liest die dort angegebenen Pflichtdokumente, implementiert die Aufgabe, validiert das Ergebnis und schreibt einen `.patch`-File in das Run-Verzeichnis.

---

## Neues Zielprojekt einrichten

1. Kopiere `targets/example.yaml` und benenne die Datei nach deinem Projekt (z. B. `targets/my-project.yaml`).
2. Passe `repo`, `base_branch`, `required_read_files`, `validation.command` und `security.deny_globs` an.
3. Lege eine Aufgaben-Datei unter `factory_tasks/my-project/task-001.md` an (nicht committed, da `factory_tasks/` in `.gitignore`).
4. Starte den External-Mode-Lauf:

```bash
python run_graph.py --external-target my-project --task factory_tasks/my-project/task-001.md
```

---

## Manifest-Felder

| Feld | Bedeutung |
|---|---|
| `repo` | SSH- oder HTTPS-URL des Ziel-Repos |
| `base_branch` | Branch, von dem aus gearbeitet wird |
| `protected_branches` | Branches, auf die nie direkt committed wird |
| `required_read_files` | Dokumente, die der Agent vor der Implementierung lesen muss (mit SHA256-Hash verifiziert) |
| `planning.architect_phase` | `disabled` deaktiviert den Architektur-Schritt für externe Targets |
| `task_sources` | Woher kommt die Aufgabe (`factory_task_file`) |
| `validation.command` | Befehl, der nach der Implementierung im Ziel-Repo ausgeführt wird |
| `builders.primary/fallback` | `claude` oder `codex` |
| `security.deny_globs` | Dateimuster, die nie in einem Patch landen dürfen |
| `security.protected_paths_in_diff` | Pfade, die der Agent nicht verändern darf |

---

## Versionsstufen

| Version | Beschreibung |
|---|---|
| **v0** (aktuell) | Kein Commit, kein Push. Der Agent liefert nur einen `.patch`-File. Mensch entscheidet, ob der Patch angewendet wird. |
| v1 | Agent darf einen Branch erstellen und committen. Kein Push. |
| v2 | Agent darf pushen und einen PR öffnen. |
| v3 | Vollautomatischer Merge nach CI-Grün. |

---

## Lokale Artefakte (nicht committed)

| Verzeichnis | Inhalt |
|---|---|
| `external_targets/<name>/` | Geklontes Ziel-Repo |
| `factory_tasks/<name>/` | Aufgaben-Dateien für das Zielprojekt |
| `runs/<name>/<run-id>/` | Patch, Reports, Logs des Laufs |

Alle drei Verzeichnisse sind in `.gitignore` eingetragen und werden nie ins Factory-Repo committed.

---

## Sicherheitsmechanismen

- **Deny-Globs:** Enthält der Ziel-Repo-Checkout Dateien, die auf `deny_globs` matchen, bricht der Lauf sofort ab.
- **Read Receipts:** Die `required_read_files` werden mit SHA256 gehasht. Weichen die Hashes beim Finalize-Schritt ab, wird kein Patch erstellt.
- **No-Commit-Policy (v0):** Der Builder darf keinen `git commit` ausführen. Versucht er es, wird der Lauf als `policy_violation` markiert.
- **Factory-Artifact-Guard:** Der Agent darf keine Factory-typischen Verzeichnisse (`reports/`, `tasks/`, `specs/`, `questions/`) im Ziel-Repo anlegen.

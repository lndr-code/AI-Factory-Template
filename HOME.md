---
tags: [home, index]
---

# AI Factory — Projektübersicht

> Navigations-Startseite des Obsidian-Vaults. Wird von Agenten nicht bearbeitet.

## Offene Tasks

```dataview
TABLE title, priority, depends_on
FROM "tasks"
WHERE status = "open" OR !status
SORT priority DESC
```

## Ausstehende Entscheidungen (ADRs)

```dataview
TABLE title, date
FROM "decisions"
WHERE status = "proposed"
SORT date DESC
```

## Offene Fragen

[[questions/open_questions]]

## Schnellzugriff

- [[specs/product_spec|Produktspezifikation]]
- [[specs/architecture|Architektur]]
- [[knowledge/glossary|Glossar]]
- [[reports/summary|Projekt-Chronik]]
- [[runbooks/setup|Setup-Anleitung]]

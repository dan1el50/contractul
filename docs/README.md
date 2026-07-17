# Documentation

Documentation for **Contracte.md** — the self-service contract platform of Crowe Turcan Mikhailenko.

> **Status: target state, not current state.**
> These documents describe the system we are building. At the time of writing, the
> repository contains only the clickable design prototype (the `*.dc.html` files at
> the repo root). Nothing described here as "backend", "frontend", or "Docker" exists
> yet — each will be built on its own branch. Where a document describes something not
> yet built, it is the specification for that work, not a report of it.

## Index

| Document | What it covers |
| --- | --- |
| [architecture.md](architecture.md) | What the system is, the services it is made of, how a request flows through them, and the reasoning behind the technology choices. Start here. |
| [project-structure.md](project-structure.md) | The full folder layout of the monorepo, what belongs in each directory, and the rules that keep it from drifting. |
| [development-setup.md](development-setup.md) | Getting the stack running locally with Docker Compose: prerequisites, first run, everyday commands, and troubleshooting. |
| [roadmap.md](roadmap.md) | The order the system gets built in, one branch per phase, and the reasoning behind that order. |

## Reading order

If you are new to the project, read them in the order above. `architecture.md` explains
*why*, `project-structure.md` explains *where*, `development-setup.md` explains *how to run
it*, and `roadmap.md` explains *what happens next*.

## Not covered yet

Deliberately left for later branches, so that they can be written against real code
rather than guesses:

- **Data model** — the PostgreSQL schema (users, templates, orders, wallet, documents).
- **API contract** — the REST endpoint specification. Until it is written, the
  auto-generated OpenAPI docs at `/docs` are the source of truth.
- **Conventions and git workflow** — branching, commits, code style, testing strategy.

## Keeping these documents honest

Documentation that lies is worse than no documentation. Two rules:

1. If a change makes a document wrong, fix the document **in the same branch** as the
   change. Not in a follow-up.
2. Do not document what the code already states plainly. These files explain decisions,
   boundaries, and reasoning — the things you cannot recover by reading the source.

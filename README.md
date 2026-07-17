# Contracte.md

A self-service shop for legal contracts, by **Crowe Turcan Mikhailenko**.

Customers choose a contract template, fill in a guided form, pay, and download the
finished document as a PDF and an editable Word file. The templates are drafted and kept
current by Crowe's lawyers, and the documents comply with the legislation of the Republic
of Moldova.

## Status

**Early. The design is done; the implementation has not started.**

What exists today is a clickable prototype of all twelve screens (the `*.dc.html` files),
built with Claude Design. It is the specification for the product, not its source code.
Open any of them directly in a browser — no tooling required. Start with `Landing.dc.html`.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Frontend | React, TypeScript, Vite |
| Orchestration | Docker Compose |
| Documents | DOCX templates, rendered and converted to PDF |

## Documentation

Start with [`docs/`](docs/README.md).

- [Architecture](docs/architecture.md) — what the system is, how it fits together, and why
  it was built that way.
- [Project structure](docs/project-structure.md) — the folder layout and the rules that
  keep it coherent.
- [Development setup](docs/development-setup.md) — running the stack locally.

## Getting started

Once the Docker setup lands, this becomes:

```bash
cp .env.example .env
docker compose up --build
```

Until then, see [development setup](docs/development-setup.md) for the plan.

## How we work

Each part of the project is built on its own branch and merged into `main` when complete.

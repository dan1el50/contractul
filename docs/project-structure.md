# Project structure

This document is the reference for **where things go**. The layout is a monorepo: one
repository holding the backend, the frontend, and the orchestration that runs them
together.

> **Target state.** Only `docs/`, the design prototype, and `README.md` exist today.
> Everything else is the specification for the branches that will build it.

## Top level

```
contractul/
├── README.md                  Orientation. What this is, how to start it.
├── docker-compose.yml         Service definitions. The base stack.
├── docker-compose.override.yml    Local dev overrides (hot reload, exposed ports).
├── .env.example               Every variable the stack reads, with safe defaults.
├── .gitignore
│
├── docs/                      This documentation.
│
├── backend/                   FastAPI application. Self-contained.
├── frontend/                  React application. Self-contained.
│
└── design/                    The design prototype. Temporary — see below.
```

Two rules for the root:

1. **The root is for orchestration, not code.** Anything the whole stack needs lives here.
   Anything one application needs lives inside that application. No stray scripts.
2. **`backend/` and `frontend/` never reach into each other.** No relative imports across
   the boundary. They communicate over HTTP, exactly as they will in production. Anything
   shared between them is shared through the API contract, not the filesystem.

## `backend/`

```
backend/
├── Dockerfile
├── pyproject.toml             Dependencies and tool configuration.
├── alembic.ini
├── alembic/
│   └── versions/              Migrations. Committed, never edited after merge.
│
├── app/
│   ├── main.py                App construction and startup. Thin.
│   │
│   ├── core/                  Cross-cutting concerns, no business logic.
│   │   ├── config.py          Settings from environment. The only place os.environ is read.
│   │   ├── security.py        Hashing, token issuing and verification.
│   │   └── logging.py
│   │
│   ├── db/
│   │   ├── base.py            Declarative base and model registry.
│   │   └── session.py         Engine and session lifecycle.
│   │
│   ├── api/
│   │   ├── deps.py            Shared dependencies (current user, db session, admin guard).
│   │   └── v1/
│   │       ├── router.py      Assembles the routes below.
│   │       └── routes/
│   │           ├── auth.py
│   │           ├── templates.py       Catalog browsing.
│   │           ├── cart.py
│   │           ├── orders.py          Checkout and order history.
│   │           ├── wallet.py          Balance, top-up, transactions.
│   │           ├── documents.py       Listing and downloading.
│   │           └── admin.py
│   │
│   ├── models/                SQLAlchemy models. One file per aggregate.
│   ├── schemas/               Pydantic request/response models. Mirrors routes/.
│   ├── services/              Business logic. One file per use case area.
│   │
│   ├── documents/             Document rendering.
│   │   ├── renderer.py        DOCX fill + PDF conversion.
│   │   └── fields.py          Placeholder definitions and validation.
│   │
│   └── integrations/          The outside world, behind interfaces.
│       ├── payments/
│       │   ├── base.py        The PaymentProvider protocol.
│       │   └── mock.py        Always-succeeds implementation.
│       └── storage/
│           ├── base.py        The Storage protocol.
│           └── local.py       Filesystem implementation.
│
├── contract_templates/        The .docx source templates, by language.
│   ├── ro/
│   ├── ru/
│   └── en/
│
└── tests/
    ├── conftest.py
    ├── unit/                  Services in isolation. No database, no network.
    └── integration/           Through the API, against a real test database.
```

### Why `api/v1/`

The version is in the path from the first commit. Adding versioning later means either
breaking every client at once or bolting on a scheme that fights the existing structure.
Starting with `v1/` costs one directory and buys the ability to ship `v2` beside it.

### Why `contract_templates/` and not `templates/`

`templates/` is the conventional name for a web framework's HTML templates. These are not
that — they are the legal documents that constitute the product. The longer name prevents
a genuinely confusing collision.

### Where a new endpoint goes

Four files, in this order:

1. `schemas/` — define what goes in and what comes out.
2. `services/` — write the logic, with no reference to HTTP.
3. `api/v1/routes/` — wire it up. The handler should be short enough to read at a glance.
4. `tests/` — unit-test the service, integration-test the route.

If step 3 grows past a few lines, the logic is in the wrong layer. Move it down to step 2.

## `frontend/`

Organised by **feature**, not by file type. A `components/` directory holding every
component in the application tells you nothing about the application; a `features/wallet/`
directory tells you the application has a wallet. The corollary is that a feature's files
live together, and deleting a feature means deleting one directory.

```
frontend/
├── Dockerfile
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
│
├── src/
│   ├── main.tsx               Entry point.
│   │
│   ├── app/
│   │   ├── router.tsx         Route definitions.
│   │   ├── providers.tsx      Context providers composed in one place.
│   │   └── layouts/           AppShell (sidebar + header), PublicLayout, AuthLayout.
│   │
│   ├── features/              Business features. The bulk of the code.
│   │   ├── auth/
│   │   ├── catalog/
│   │   ├── contract/
│   │   ├── cart/
│   │   ├── documents/
│   │   ├── wallet/
│   │   ├── settings/
│   │   └── admin/
│   │       Each contains, as needed:
│   │         components/   Components used only by this feature.
│   │         api.ts        Its API calls.
│   │         types.ts      Its types.
│   │         hooks.ts      Its stateful logic.
│   │
│   ├── components/ui/         Generic, feature-agnostic primitives:
│   │                          Button, Card, Input, Badge, Modal, Chip.
│   │                          Nothing here may import from features/.
│   │
│   ├── lib/
│   │   ├── api-client.ts      HTTP client, auth headers, error normalisation.
│   │   ├── format.ts          Money and date formatting. MDL rules live here, once.
│   │   └── i18n/              RO / RU / EN interface strings.
│   │
│   ├── styles/
│   │   ├── tokens.css         Design tokens. See the architecture design system table.
│   │   └── global.css
│   │
│   └── assets/                Brand images, carried over from the prototype.
│
└── tests/
```

### The dependency rule

Dependencies flow in one direction only:

```
app/  ──▶  features/  ──▶  components/ui/  ──▶  lib/
```

- `components/ui/` must never import from `features/`. A `Button` that knows about wallets
  is not a `Button`.
- Features should not import from each other. If two need the same thing, it belongs in
  `components/ui/` or `lib/`.
- No colour, spacing, or font literals outside `styles/tokens.css`. The prototype hardcodes
  every value inline — appropriate there, unmaintainable here. A brand tweak must be one
  edit.

## The design prototype

The twelve `*.dc.html` files currently at the repository root are a clickable prototype
built with Claude Design. They are the **specification** for the frontend: the screens,
the flows, the visual system, and the copy.

They are **not source code and none of it carries over.** They run on `support.js`, a
React-based prototype runtime that has nothing to do with our React application.

Planned handling:

1. **Now** — they stay at the root, untouched. They still need to be openable.
2. **When frontend work starts** — they move to `design/` so the root reflects the real
   structure. Move them together with `support.js` and `assets/` so the relative paths
   keep working. `uploads/` (the Crowe brand PDFs) moves there too.
3. **When a screen is implemented in React** — the corresponding `.dc.html` is deleted in
   the same PR. The React implementation replaces it; keeping both invites drift, and a
   stale prototype is worse than no prototype because people trust it.
4. **When the last screen ships** — `design/` is deleted entirely. `assets/` graduates to
   `frontend/src/assets/`.

Brand assets survive this. The prototype does not.

## Conventions worth stating

**Naming.** Python uses `snake_case` files and modules. React components are
`PascalCase.tsx`; everything else in the frontend is `kebab-case.ts`. Directories are
lowercase.

**Environment variables.** Every one is listed in `.env.example` with a safe default.
`.env` is never committed. `app/core/config.py` is the only place the backend reads the
environment — everything else takes settings as arguments, which is what makes it testable.

**Tests mirror source.** `tests/unit/services/test_wallet.py` tests
`app/services/wallet.py`. Finding the test for a file should require no searching.

**Migrations are append-only.** Once a migration is merged, it is never edited. Correcting
it means writing another one. Someone else's database has already run it.

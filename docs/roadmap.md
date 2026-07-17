# Roadmap

The order in which Contracte.md gets built, and why that order.

Each phase is one branch, merged into `main` when complete. A phase is done when it works
end to end — not when the code is written.

## The shape of the plan

Two principles decide the order.

**Vertical slices, not horizontal layers.** We do not build the whole backend and then the
whole frontend. Each feature phase goes all the way down: database, API, screen. Building
horizontally means discovering whether the halves fit together at the very end, and
writing endpoints against guesses about what the screens need. Building vertically means
every phase ends with something demonstrable.

**Riskiest thing first.** Most of this plan is conventional web work we can be confident
about. One part is not: rendering `.docx` to PDF with headless LibreOffice, in three
languages. That uncertainty is therefore scheduled second, before anything is built on top
of it. A surprise there changes the architecture; a surprise in the catalog does not.

## Phases

### 0 — Walking skeleton

**Branch:** `feat/walking-skeleton`

All four services in Docker Compose, one real request travelling through every one of
them. No features.

- `docker-compose.yml` + local override, `.env.example`, `.gitignore`
- FastAPI application with a health endpoint that queries PostgreSQL
- Alembic wired up, one migration applied
- React + Vite + TypeScript application that calls the health endpoint and renders it
- Hot reload working on both sides

**Done when:** `docker compose up` from a clean clone serves a page whose contents came
out of the database.

**Why first:** every integration problem — container networking, CORS, the database URL,
volume mounts — surfaces here, while there is nothing else to untangle it from. Every later
phase fills in a shape already proven to hold.

### 1 — Rendering spike ✅ DONE

**Branch:** `spike/document-rendering`

**Result: the approach works.** Proven against a real bilingual RO/RU document with
embedded screenshots — layout, images, page count, every Romanian diacritic, and Cyrillic
all survive conversion. LibreOffice adds ~4 minutes to the image build.

Delivered:

- `libreoffice-writer`, `poppler-utils`, and the DejaVu/Liberation fonts in the backend image
- `app/documents/renderer.py` — fill with `docxtpl`, convert with headless LibreOffice,
  rasterise previews with `pdftoppm`
- `tests/integration/test_renderer.py` — reads text back out of the produced PDF and
  asserts the characters survived

Two findings worth carrying forward:

- **Font substitution is silent.** A missing glyph becomes a box, the conversion reports
  success, and nothing raises. The font packages in the Dockerfile are load-bearing, and
  the tests assert on extracted PDF text rather than on the file existing — a test that
  checks only for a PDF passes on exactly this failure.
- **The fixture is not enough on its own.** It is typed without diacritics and has no
  placeholders, so it proves neither. A synthetic template covers both. When the real
  templates arrive, check what they actually contain before trusting a green suite.

The spike went further than planned — it was promoted into real code rather than thrown
away, and its output drives the prototype's document preview. Phase 7 wires it to orders
and storage.

### 2 — Data model ✅ DONE

**Branch:** `feat/data-model`

The whole schema is designed and written down in [data-model.md](data-model.md); only
`users` is implemented, because that is all phase 3 needs.

Delivered:

- `docs/data-model.md` — every table, the constraints, and the reasoning
- `users` table, migration `0002_users`, verified to upgrade and downgrade cleanly
- Deterministic constraint naming on `Base.metadata`, set now while there is one table
  rather than later when every constraint would need renaming
- A database test harness: a throwaway `contractul_test` database, and a per-test
  transaction that is always rolled back so tests cannot depend on execution order

Three open questions are recorded at the bottom of the data model rather than guessed at:
**VAT** (needed before phase 6), **order numbering** (gap-free numbering is far harder
than it looks), and **refunds** (nobody has specified who may issue one).

### 3 — Authentication

**Branch:** `feat/auth`

Registration, login, sessions, the current-user dependency, and the `Autentificare` screen.

**Done when:** you can register, log in, and see your own name in the app shell.

**Why here:** every phase downstream needs to know who the user is. It is also
well-understood work, which makes it the right place to establish the patterns — how a
service is shaped, how a route stays thin, how tests are written — that the rest of the
codebase will copy.

### 4 — Catalog

**Branch:** `feat/catalog`

The first true vertical slice.

- Template catalog endpoints, category filtering, flat per-document pricing
- Real document previews, rendered on demand via the phase 1 renderer, replacing the
  committed PNGs the prototype uses
- `Landing`, `Catalog Sabloane`, `Detaliu Contract` screens
- Design tokens extracted into `styles/tokens.css`
- The app shell: sidebar and header

**Retires:** `Landing.dc.html`, `Catalog Sabloane.dc.html`, `Detaliu Contract.dc.html`,
`Sidebar.dc.html`

**Done when:** you can browse the real catalog and open a real contract.

**Why here:** read-only, so no transactional complexity. The point is to prove the slice
pattern and settle the design system, not to fight the hard problems yet.

### 5 — Wallet

**Branch:** `feat/wallet`

- The append-only transaction ledger; balance derived from it, never stored mutable
- Top-up against `MockPaymentProvider`
- `Portofel` and `Adauga Card` screens

**Retires:** `Portofel.dc.html`, `Adauga Card.dc.html`

**Done when:** you can top up and watch the balance and history change.

### 6 — Cart and checkout

**Branch:** `feat/checkout`

The money path.

- Server-side cart
- Checkout in a single transaction: verify balance, debit wallet, record order
- `Cos` and `Confirmare` screens

**Retires:** `Cos.dc.html`, `Confirmare.dc.html`

**Done when:** a purchase either fully happens or fully does not, proven by a test that
fails mid-transaction.

**Note:** the prototype's cart and confirmation screens disagree with each other — the
cart checks out two items for 1 700 MDL, the receipt shows one for 900. Resolve this
deliberately when building; do not copy either side by accident.

### 7 — Document generation

**Branch:** `feat/documents`

The payoff. The first point where the product does the thing it exists to do.

- Promote the phase 1 spike into a real renderer behind an interface
- Generate on order completion, outside the payment transaction
- Store immutably, version the template used
- Download endpoints with authorisation
- `Documentele Mele` screen

**Retires:** `Documentele Mele.dc.html`

**Done when:** you can buy a contract and download a correct PDF and Word file.

**Depends on:** real `.docx` templates from the legal team. See below.

### 8 — Settings

**Branch:** `feat/settings`

Profile, company data, saved cards, notification preferences, password.

**Retires:** `Setari.dc.html`

### 9 — Admin

**Branch:** `feat/admin`

KPIs, revenue chart, order queue, template management.

**Retires:** `Dashboard Admin.dc.html`. `design/` is deleted; `assets/` graduates to
`frontend/src/assets/`.

**Why last:** it is internal. Nobody outside Crowe is blocked on it, which also makes it
the easiest scope to cut if we run long.

### 10 — Real payments

**Branch:** `feat/payments-maib`

Replace `MockPaymentProvider` with a real acquirer. Scheduled by when credentials arrive,
not by readiness.

The interface means no business logic changes. It does not mean no surprises — 3-D Secure
redirects, webhook timing, and currency handling are things a mock cannot teach us.

## The dependency that is not code

**The legal team must draft the `.docx` templates.**

Each template is one file containing every language it is written in — Romanian and
Russian side by side on the page, not three separate files.

Start this conversation now. It sits on no branch's critical path and squarely on the
critical path of shipping. We cannot sell a contract that does not exist, and "a lawyer
finds time to draft twelve multilingual contracts" is measured in weeks and is entirely
outside our control.

Phase 1 is done and used a stand-in fixture. Phase 7 needs the real ones. The
lead time starts when we ask, not when we are ready.

## What this plan assumes

**One developer.** If a second joins, the order changes: settle a slice's API contract
first, then build both sides against it in parallel. That is the case where
`docs/api-contract.md` stops being optional — with one developer it is documentation, with
two it is coordination.

**Phases can be resequenced; phase 0 and phase 1 cannot.** Everything from phase 3 onward
is negotiable if priorities shift. The skeleton and the spike are not, because they exist
to remove uncertainty that everything else assumes away.

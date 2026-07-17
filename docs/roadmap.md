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

### 1 — Rendering spike

**Branch:** `spike/document-rendering`

Prove that a `.docx` can be filled and converted to PDF inside the backend container.
Timeboxed. Throwaway code, no API, no polish.

- LibreOffice headless in the backend image
- Fill one sample template with `docxtpl`, convert the result to PDF
- **Verify Romanian diacritics (ă î ș ț â) and Cyrillic render correctly in both outputs**
- Measure how long a conversion takes

**Done when:** we can state with evidence that the approach works, or that it does not.

**Why second:** this is the product. Everything else on this list is work we know how to
do; this is the one dependency that could force an architecture change, and finding that
out after building a catalog and a checkout would be expensive. The font handling in
headless LibreOffice is the specific risk — Romanian diacritics and Cyrillic in the same
document is exactly where it tends to break.

A negative result here is a success for the phase. It is far cheaper now than in phase 7.

### 2 — Data model

**Branch:** `feat/data-model`

Design the **whole** schema — users, templates, orders, wallet ledger, documents — and
write it down. Implement migrations only for what phase 3 needs.

Designing all of it upfront prevents rework, because the shape of the money side
constrains everything around it. Implementing all of it upfront builds tables for
features that are not yet specified.

**Done when:** the schema is documented in `docs/data-model.md` and the users table exists.

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

- Template catalog endpoints, category filtering, language pricing
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

**The legal team must draft the `.docx` templates, in three languages.**

Start this conversation in parallel with phase 0. Not phase 7.

It sits on no branch's critical path and squarely on the critical path of shipping. We
cannot sell a contract that does not exist, and "a lawyer finds time to draft twelve
contracts in three languages" is measured in weeks and is entirely outside our control.

Phase 1 needs only one rough template to spike against. Phase 7 needs all of them. The
lead time starts when we ask, not when we are ready.

## What this plan assumes

**One developer.** If a second joins, the order changes: settle a slice's API contract
first, then build both sides against it in parallel. That is the case where
`docs/api-contract.md` stops being optional — with one developer it is documentation, with
two it is coordination.

**Phases can be resequenced; phase 0 and phase 1 cannot.** Everything from phase 3 onward
is negotiable if priorities shift. The skeleton and the spike are not, because they exist
to remove uncertainty that everything else assumes away.

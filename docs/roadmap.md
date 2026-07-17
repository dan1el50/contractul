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

### 3 — Authentication ✅ DONE

**Branch:** `feat/auth`

Registration, login, logout, sessions, the current-user dependency, and the
`Autentificare` screen. Verified in a real browser: register, reload, log out, and be
refused on the way back in.

**Retires:** `Autentificare.dc.html`

Delivered:

- `sessions` table — server-side, not JWT, because revocation has to be immediate
- Argon2id hashing; session tokens SHA-256'd before storage
- httpOnly + SameSite=Lax cookie. The browser check confirms `document.cookie` is empty
  while the session works — JavaScript cannot reach it, so XSS cannot steal it.
- One indistinguishable failure for unknown email / wrong password / deactivated account,
  including matching timing
- React Router, an auth context, a `RequireAuth` gate, and the real login screen

The patterns the rest of the codebase copies are set here: services know nothing about
HTTP, routes are three lines, schemas list their fields explicitly so a model column can
never leak into a response by accident.

Two things this phase turned up, both recorded where they happened:

- **The phase 2 schema forgot sessions**, despite claiming to be complete. Designing a
  schema "whole" is not the same as designing it correctly.
- **A circular import meant the server would not start, and 83 tests passed anyway.**
  Import order in `conftest.py` differed from uvicorn's. `tests/unit/test_app_imports.py`
  now imports `app.main` in a fresh subprocess, and was verified to fail against the
  original bug — a guard nobody has watched fail is not a guard.

### 4 — Catalog ✅ DONE

**Branch:** `feat/catalog`, `feat/landing`

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

**Status: done.** The catalog, detail page, app shell, previews and tokens were built
first; the public `Landing` page finished the phase on `feat/landing`, moving the catalog
out from behind `RequireAuth`.

How the public/private split settled:

- **`/` is the public Landing page**, in a new `PublicLayout` (top nav + footer). Its hero
  counts and category prices are read live from the catalog — the prototype's invented
  "36+ tipuri / 1 480+ vândute" are gone, as are its "20% bonus" and "factură fiscală"
  claims, which describe things we do not offer (see the wallet and numbering decisions).
- **The catalog and detail pages are now public**, since a shop you must log in to browse
  is a shop nobody browses. They use `BrowseLayout`, which picks chrome by auth state:
  the sidebar `AppShell` when signed in, `PublicLayout` when signed out. Verified in a
  real browser both ways. The wallet stays behind `RequireAuth`.
- **The brand textures graduated** from the prototype's `assets/` into
  `frontend/src/assets/`, as planned.

**The paywall, as built.** Locked preview pages are rendered at 18 dpi and never at full
resolution. The design's CSS blur is decoration over an image that is already unreadable —
verified in a browser, where page 1 loads 910px wide and page 2 loads 149px. If that blur
were the protection, deleting one style rule would give the document away.

### 5 — Wallet ✅ DONE

**Branch:** `feat/wallet`

Balance, top-ups, saved cards, and history. Verified in a browser: add a card, top up
2 000 MDL, watch the balance and history change, and have a declined card refused.

**Retires:** `Portofel.dc.html`, `Adauga Card.dc.html`

Delivered:

- `wallet_transactions` (append-only, no balance column) and `payment_cards`
- `PaymentProvider` behind an interface; `MockPaymentProvider` with test cards
- `debit()` with a row lock — the primitive phase 6 checkout will use
- Wallet and card endpoints, `Portofel` and `Adauga Card` screens

Three things worth carrying forward:

- **The concurrency guard took three attempts to make real.** Racing two tasks with
  `asyncio.gather` passed with the lock removed — the interleaving never happened.
  Asserting `SELECT … FOR UPDATE NOWAIT` was refused *also* passed with the lock removed,
  because inserting a row with a foreign key takes a `FOR KEY SHARE` lock on the parent by
  itself; the test was measuring PostgreSQL, not us. The surviving test forces the ordering
  and is verified to fail when the lock is deleted.
- **`now()` is the transaction start time**, so ledger rows written together shared a
  timestamp and ordered non-deterministically. Wallet entries use `clock_timestamp()`.
- **Card details reach our server**, which is a development-only shortcut. A real acquirer
  tokenises in the browser and the PAN never touches us — that is what keeps this out of
  PCI-DSS scope. Phase 10 deletes the server-side path rather than reimplementing it.

The prototype's "bonus până la 20% la alimentare" is **not** implemented. Nobody specified
a bonus scheme, and inventing one in the UI would be inventing a business rule.

### 6 — Cart and checkout ✅ DONE

**Branch:** `feat/checkout`

The money path. Verified end to end in a real browser: fund the wallet, add a contract,
pay from the wallet, land on a receipt with a real order number.

**Retires:** `Cos.dc.html`, `Confirmare.dc.html`

Delivered:

- `carts`/`cart_items` and `orders`/`order_items`, migration `0006_orders`, and a plain
  PostgreSQL sequence for `CT-{year}-{n}` numbers (gaps allowed, as decided)
- A server-side cart that holds template ids and reads prices live from the catalog
- `checkout()` in one transaction: snapshot the lines, create the order, debit the wallet,
  empty the cart — all or nothing
- Cart, order, and money schemas with the VAT split derived for display
- `Coș` and `Confirmare` screens, a cart context feeding a sidebar badge, and the detail
  page's "add to cart" wired up

Four things worth carrying forward:

- **Atomicity is proven against a real connection, not the shared test session.** The shared
  session's `commit` is not a durable boundary, so a rollback there erases the test's own
  setup; proving a rollback restores a *committed* balance needs separate transactions. Two
  tests do it: an insufficient-funds failure (which fails after the order is flushed) and an
  injected failure *after* a successful debit — the harder case, where the money must come
  back with the order.
- **The renderer serialised a lazy relationship outside async context.** Building the order
  response touched `order.items`, which triggered a lazy load and a `MissingGreenlet`. Fixed
  by populating the collection through the relationship, and `paid_at` is a real datetime,
  not an unresolved `func.now()`.
- **The prototype's cart and confirmation disagreed** — the cart totals two items at
  1 700 MDL, the receipt shows one at 900. Neither was copied; both screens read the real
  order.
- **The confirmation screen is honest about phase 7.** No document downloads (not built),
  no "factură fiscală" (we issue none), and the method is the wallet, not a card.

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

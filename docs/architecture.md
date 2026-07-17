# Architecture

## What we are building

Contracte.md is a self-service shop for legal contracts. A customer picks a contract
template, fills in a guided form, pays for it, and downloads the finished document as a
PDF and an editable Word file. The templates are drafted and kept current by the lawyers
of Crowe Turcan Mikhailenko, and the documents comply with the legislation of the
Republic of Moldova.

The product exists because the alternative — engaging a lawyer for a standard contract —
is slow and expensive relative to the work involved. The platform sells the lawyers'
judgment once, as a template, and then delivers it many times without their involvement.

### Who uses it

- **Customers** — mostly Moldovan businesses (SRLs) and individuals who need a standard
  contract quickly. They browse the catalog, buy, and download.
- **Administrators** — Crowe staff. They maintain the template catalog, review the order
  queue, and monitor revenue.

### What shapes the design

Four properties of the domain drive most of the decisions below.

- **Documents are the product.** Rendering must be correct, reproducible, and auditable.
  A document that was sold must remain byte-for-byte retrievable years later, even after
  its template has been revised.
- **Money is involved.** Wallet balances and payments need transactional integrity. This
  is the main reason for a relational database.
- **Multilingual documents, sold whole.** A document contains every language it is written
  in, in one file — Romanian and Russian side by side on the page. It is one indivisible
  product at one price; the buyer does not choose a language, because there is nothing to
  choose. This makes rendering harder, not easier: two scripts must survive in the same
  PDF, and a font covering only Latin silently destroys half of every document.
- **Moldovan payments are awkward.** Local acquirers are the eventual target, so the
  payment integration is isolated behind an interface from day one.

## System overview

Four services, orchestrated by Docker Compose. In production, `frontend` becomes a static
bundle behind a reverse proxy rather than a dev server.

```
                    ┌──────────────┐
   Browser ────────▶│   frontend   │   React + Vite + TypeScript
                    │  (port 5173) │   SPA, talks to the API over HTTP
                    └──────┬───────┘
                           │  JSON / REST
                           ▼
                    ┌──────────────┐
                    │   backend    │   Python + FastAPI
                    │  (port 8000) │   API, business logic, doc rendering
                    └──┬────────┬──┘
                       │        │
          SQLAlchemy   │        │  file writes
                       ▼        ▼
              ┌──────────────┐ ┌──────────────┐
              │   database   │ │   storage    │
              │ (PostgreSQL) │ │ (volume)     │
              │  port 5432   │ │ generated    │
              └──────────────┘ │ documents    │
                               └──────────────┘
```

### Services

**`frontend`** — A React single-page application built with Vite and TypeScript. It holds
no business logic and no secrets; it renders state and calls the API. It is a direct
translation of the existing design prototype, so the visual system is already settled
(see [Design system](#design-system) below).

**`backend`** — A FastAPI application. It owns every rule in the system: what a document
costs, whether a wallet has sufficient funds, who may download what, and how a template
becomes a document. If a rule matters, it lives here — never in the frontend, which is
merely a convenient client that an attacker can bypass.

**`database`** — PostgreSQL. Chosen because the core of this product is money and orders,
and those need transactions, foreign keys, and constraints that the database itself
enforces. A wallet debit and an order record must commit together or not at all; that is
a database guarantee, not something to hand-roll in application code.

**`storage`** — A Docker volume holding rendered documents and uploaded `.docx` templates.
A volume is the pragmatic starting point; the code reaches it through a storage interface
so that moving to S3-compatible object storage later is a configuration change rather
than a rewrite. See [Replaceable edges](#replaceable-edges).

## Backend layering

The backend is layered, and the layers only ever call downward:

```
  api/          HTTP concerns only — routing, request/response shapes, auth guards.
    │           Knows about FastAPI. Knows nothing about SQL.
    ▼
  services/     Business logic. "Buying a contract" lives here, whole.
    │           Knows nothing about HTTP. Framework-agnostic and directly testable.
    ▼
  models/       SQLAlchemy ORM models — the database schema in Python.
```

Two supporting layers sit alongside:

- **`schemas/`** — Pydantic models defining what crosses the API boundary. Deliberately
  separate from `models/`: the shape you store and the shape you expose should be free to
  differ, and coupling them leaks database columns into your public contract.
- **`integrations/`** — everything that talks to the outside world (payments, storage),
  each behind an interface.

The point of the layering is that **a route handler should read like a summary**: check
permission, call one service, return a schema. When a handler starts doing arithmetic or
opening transactions, the logic belongs in a service.

## Key flows

### Buying a contract

The load-bearing flow of the product, and the one where correctness matters most.

1. Customer selects a template. One template is one priced line item — the languages it
   contains are a property of the document, not a choice.
2. Items go into a cart. The cart is **server-side state**, not browser state — a price
   the client can edit is not a price.
3. At checkout the customer pays from their wallet balance or by card.
4. The backend, **in a single database transaction**, verifies the balance, debits the
   wallet, and records the order. Either all of it happens or none of it does. A wallet
   that is debited without an order, or an order without payment, are both unacceptable
   outcomes and the transaction is what rules them out.
5. Only after that transaction commits does rendering begin — the customer's data is
   merged into the `.docx` template, and the result is converted to PDF.
6. Both files are written to storage and linked to the order. The customer downloads them.

Rendering is deliberately **outside** the payment transaction. Document generation is slow
and can fail for reasons that have nothing to do with money (a malformed template, a
LibreOffice crash), and none of those reasons should be able to roll back a completed
payment. A paid order whose document failed to render is a recoverable state: retry the
render. A lost payment is not.

### Topping up the wallet

The wallet exists so customers pay once and buy repeatedly. A top-up charges the payment
provider and, on success, credits the balance.

The balance is **never stored as a mutable number that gets overwritten**. It is derived
from an append-only ledger of transactions. This costs a little query complexity and buys
a great deal: every balance is explainable, the transaction history in the UI is the
source of truth rather than a parallel record that can drift, and a bug can be diagnosed
after the fact instead of merely observed.

### Rendering a document

Chosen approach: **DOCX templates → filled → converted to PDF.**

Lawyers author templates in Word with named placeholders. The backend fills them using
`docxtpl`/`python-docx`, then converts to PDF with headless LibreOffice inside the backend
container.

The reasoning: the people who own the content are lawyers, not developers. If templates
were HTML, every legal wording change would require a developer. With `.docx`, a lawyer
edits a Word file. It also means the Word output we sell is a *real* Word document rather
than a reconstruction — and "editable Word" is an advertised feature, so it needs to be
genuinely good.

The cost is that LibreOffice is a heavy dependency in the image and PDF conversion is
slow. That is an acceptable trade for content the legal team can own directly.

**Verified.** The phase 1 spike proved this works, against a real bilingual RO/RU document
with embedded screenshots: layout, images, page count, Romanian diacritics, and Cyrillic
all survive conversion. LibreOffice adds roughly four minutes to the image build.

The specific hazard, now guarded by tests: **font substitution is silent.** LibreOffice
swaps a missing font for whatever it has, and a glyph it cannot render becomes a box or
`U+FFFD` — the conversion reports success and the document is ruined. Two consequences
that must not be undone:

- The font packages in `backend/Dockerfile` are load-bearing, not incidental. DejaVu and
  Liberation are there because they cover Latin Extended-A and Cyrillic.
- `tests/integration/test_renderer.py` reads text back out of the produced PDF and asserts
  the characters survived. A test that merely asserts a PDF exists would pass on exactly
  the failure worth catching.

Two rules protect the archive:

- **Templates are versioned.** An order records the exact template version it used.
  Revising a template never alters a document already sold.
- **Rendered documents are immutable.** Once written, a file is never modified. Fixing a
  bad document means producing a new one, not editing the old one.

## Replaceable edges

Anything that will plausibly change is placed behind an interface, so that changing it
touches one file rather than the whole codebase.

### Payments

The first implementation is a **mock provider that always succeeds**, so the entire
purchase flow can be built and tested without merchant credentials. Real integration with
a Moldovan acquirer (MAIB, Paynet) comes later.

This is only safe because of the interface:

```python
class PaymentProvider(Protocol):
    def charge(self, amount: Money, method: PaymentMethod) -> PaymentResult: ...
    def refund(self, charge_id: str) -> RefundResult: ...
```

`MockPaymentProvider` implements it now; a real provider implements it later. Services
depend on the protocol and are injected with an implementation, so **no business logic
changes when the real gateway arrives.** The mock is also what the test suite uses
permanently — tests must never touch a real acquirer.

The rule that makes this work: nothing outside `integrations/payments/` may import a
concrete provider. If a service imports `MockPaymentProvider` by name, the abstraction is
already broken.

### Storage

Same pattern. A `Storage` interface with `save`, `open`, and `delete`; a local-filesystem
implementation now, an S3 implementation when we deploy somewhere that warrants it.

## Design system

The visual language is settled and comes from the Crowe brand, already applied across the
twelve prototype screens. The React implementation must extract these into tokens rather
than repeat literals — the prototype hardcodes them inline, which is correct for a
prototype and wrong for a product.

| Token | Value | Used for |
| --- | --- | --- |
| Navy | `#011E41` | Primary. Sidebar, headings, dark sections. |
| Amber | `#F5A800` | Calls to action. |
| Teal | `#0C7876` | Success, "verified by Crowe". |
| Blue | `#003F9F` / `#0075C9` | Links and informational accents. |
| App background | `#EEF1F5` | Canvas behind cards. |
| Card border | `#E6E9EE` | Card and divider strokes. |
| Typography | Helvetica Neue | Whole interface. |

Cards use 14–16px radii. Icons are inline Feather-style SVG strokes. The
`assets/smartpath-*.png` textures are Crowe brand assets and carry over as-is.

The prototype's twelve screens map to the application's routes: a public landing page and
authentication, a customer area (catalog, contract detail, cart, confirmation, my
documents, wallet, settings, add card), and an admin dashboard.

The `*.dc.html` files are **the specification, not the source.** They are a React-based
prototype runtime (`support.js`) and none of that code carries over. They will be deleted
once the frontend implements them — see
[project-structure.md](project-structure.md#the-design-prototype).

## Decisions and their trade-offs

| Decision | Why | What it costs |
| --- | --- | --- |
| **Monorepo** | One PR can change an endpoint and its caller together, and the stack starts with one command. At this size, coordinating two repos is pure overhead. | Must be disciplined that shared tooling does not quietly couple the two applications. |
| **PostgreSQL** | Money and orders need real transactions and constraints. | None worth noting at this scale. |
| **Docker Compose** | Identical environment for everyone; LibreOffice and PostgreSQL never get installed by hand. | A container layer to learn, and slower feedback than running natively. |
| **Mock payments first** | Builds the whole flow without merchant credentials, which are slow to obtain. | Real integration will surface issues the mock cannot predict — 3-D Secure redirects, webhook timing, currency handling. The interface limits the blast radius but does not eliminate it. |
| **DOCX → PDF** | Lawyers own the templates without developer involvement; the Word output is genuinely native. | LibreOffice is a heavy image dependency and conversion is slow. |
| **Ledger-derived balances** | Every balance is explainable and auditable. | Slightly more complex queries than a mutable balance column. |
| **Server-side cart** | A client-side price is not a price. | An extra round trip per cart change. |
| **REST over GraphQL** | The screens are conventional and well-served by resource endpoints; FastAPI gives us OpenAPI documentation for free. | Some screens will over-fetch a little. Not worth a GraphQL layer to avoid. |

## Constraints to respect

- **Currency is MDL**, always. Money is stored as integers in minor units. Never floats —
  binary floating point cannot represent decimal currency exactly, and rounding errors in
  a wallet are real money.
- **Romanian is the primary interface language.** Not an afterthought to be retrofitted.
- **Documents are legal instruments.** Sold documents are immutable and permanently
  retrievable.
- **The frontend is not a security boundary.** Every rule is enforced server-side.

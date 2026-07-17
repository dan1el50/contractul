# Data model

The PostgreSQL schema: every table, why it exists, and the rules the database itself
enforces.

> **Status.** The whole schema is designed here; it is implemented incrementally, one
> phase at a time. Designing it whole prevents rework — the shape of the money side
> constrains everything around it. Implementing it whole would mean building tables for
> features that are not yet specified.
>
> Implemented so far: `users`, `sessions`. Everything else is the specification for its
> phase.

## Principles

Five rules that the rest of this document follows from.

**Money is integers, in bani.** 1 MDL = 100 bani, so 900 MDL is stored as `90000`. Never
floats: binary floating point cannot represent decimal currency exactly, and a rounding
error in a wallet is real money. Every money column is `BIGINT` and named `*_bani` so the
unit is impossible to misread at a call site.

**The database enforces what must be true.** Foreign keys, unique constraints, and check
constraints are not documentation — they are the last line of defence, and the only one
that holds when application code has a bug. If a rule can be expressed as a constraint, it
is one.

**Sold documents are immutable.** An order records the exact template version it was
generated from. Revising a template never alters a document already sold. Once a rendered
file is written it is never modified.

**History is append-only.** The wallet is a ledger, not a number. Nothing that records
what happened is ever updated in place.

**Purchases snapshot what they bought.** Order lines copy the price and name at the moment
of purchase. A template renamed or repriced in 2027 must not silently rewrite a 2026
receipt.

## Conventions

| Convention | Choice | Why |
| --- | --- | --- |
| Primary keys | `UUID`, `gen_random_uuid()` | Appear in URLs. Sequential integers would let anyone enumerate our customers, and let a competitor read our order volume off a receipt. |
| Timestamps | `TIMESTAMPTZ`, never `TIMESTAMP` | `TIMESTAMP` silently drops the offset. Moldova observes DST, so a naive timestamp is ambiguous twice a year. |
| Money | `BIGINT`, suffix `_bani` | See above. |
| Deletes | Soft, where history matters | An order referencing a hard-deleted template is a broken receipt. |
| Enums | `TEXT` + `CHECK` | A Postgres `ENUM` needs a migration to add a value and cannot drop one. A check constraint is a one-line change. |

## Overview

```
                      ┌───────────┐
                      │   users   │
                      └─────┬─────┘
         ┌──────────────────┼──────────────────┬────────────────┐
         │                  │                  │                │
   ┌─────▼──────┐   ┌───────▼────────┐  ┌──────▼──────┐  ┌──────▼───────┐
   │ companies  │   │ payment_cards  │  │    carts    │  │ wallet_      │
   │   (0..1)   │   │               │  │    (0..1)   │  │ transactions │
   └────────────┘   └───────────────┘  └──────┬──────┘  │  (ledger)    │
                                              │         └──────┬───────┘
                                       ┌──────▼──────┐         │
                                       │ cart_items  │         │
                                       └─────────────┘         │
                                                               │
   ┌────────────┐    ┌──────────────────┐            ┌─────────▼────┐
   │ categories │◄───┤contract_templates│            │    orders    │
   └────────────┘    └────────┬─────────┘            └──────┬───────┘
                              │                             │
                     ┌────────▼──────────┐          ┌───────▼───────┐
                     │ template_versions │◄─────────┤  order_items  │
                     └───────────────────┘          └───────┬───────┘
                                                            │
                                                    ┌───────▼───────┐
                                                    │   documents   │
                                                    └───────────────┘
```

## Tables

### `users` — implemented (phase 2)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `email` | TEXT UNIQUE NOT NULL | Stored lowercase; see below. |
| `password_hash` | TEXT NOT NULL | Argon2. Never the password. |
| `full_name` | TEXT NOT NULL | |
| `phone` | TEXT NULL | Optional; not every buyer gives one. |
| `is_admin` | BOOLEAN NOT NULL DEFAULT false | Crowe staff. |
| `is_active` | BOOLEAN NOT NULL DEFAULT true | Deactivate rather than delete — a deleted user orphans orders. |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

**Email is stored lowercase, with a plain unique constraint.** `Ion@example.md` and
`ion@example.md` are the same person, and letting both register creates an account someone
cannot log into. The alternative — the `citext` extension — pushes the rule into the
database but costs an extension we would otherwise not need; normalising on write is
enough provided it happens in exactly one place.

**`is_admin` is a boolean, not a role table.** There are two kinds of people here:
customers and Crowe staff. A roles-and-permissions system would be built for a requirement
nobody has stated. It becomes a table the day a third kind appears.

### `sessions` — implemented (phase 3)

A signed-in session. **Missed when this schema was first designed** — phase 2 claimed to
cover "the whole schema" and did not think about how anyone stays logged in. Added in
phase 3, where the omission became obvious.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `token_hash` | TEXT(64) UNIQUE NOT NULL | SHA-256 of the token. Never the token. |
| `user_id` | UUID FK → users ON DELETE CASCADE | |
| `expires_at` | TIMESTAMPTZ NOT NULL | 30 days from creation. |
| `revoked_at` | TIMESTAMPTZ NULL | Set on logout. |
| `created_at` | TIMESTAMPTZ NOT NULL | |

Index: `(user_id, expires_at)` — every authenticated request filters on it.

**Server-side sessions, not JWT.** The deciding factor is revocation. Deactivating an
account or logging out must take effect immediately, and a stateless token stays valid
until it expires no matter what the database says. The standard remedy — a revocation list
— is this table with extra steps and worse ergonomics. The cost is one indexed lookup per
authenticated request, which at this scale is nothing.

**Tokens are hashed, exactly like passwords.** Someone who reads this table must not come
away with a working login for every user currently signed in. Plain SHA-256 rather than
Argon2, deliberately: Argon2 is slow to frustrate guessing a low-entropy human password,
whereas a session token is 32 random bytes — already unguessable — and this is read on
every request, so slowness would buy nothing and cost everything.

**The only `ON DELETE CASCADE` in the schema.** A deleted user's sessions are meaningless.
Everywhere else, history outlives its subject and deletes are soft.

### `companies` — phase 8

One per user, optional. The buyer may be an individual.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK → users UNIQUE | Unique makes it one-to-one. |
| `name` | TEXT NOT NULL | `SRL "NordConstruct"` |
| `idno` | TEXT NOT NULL | Moldovan company identifier, 13 digits. |
| `legal_address` | TEXT | |
| `iban` | TEXT | |
| `bank_name` | TEXT | |

Separate from `users` rather than nullable columns on it: a company is a distinct thing
with its own required fields. As columns, "either all null or all present" is a rule no
constraint can express cleanly.

### `categories` — phase 4

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `slug` | TEXT UNIQUE NOT NULL | `servicii`. Used in URLs. |
| `name` | TEXT NOT NULL | `Servicii & Colaborare` |
| `description` | TEXT | |
| `sort_order` | INT NOT NULL DEFAULT 0 | Admin controls catalog order. |

### `contract_templates` — phase 4

A product in the catalog.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `category_id` | UUID FK → categories | |
| `slug` | TEXT UNIQUE NOT NULL | |
| `name` | TEXT NOT NULL | |
| `description` | TEXT NOT NULL | |
| `price_bani` | BIGINT NOT NULL CHECK (> 0) | Flat. 900 MDL = `90000`. |
| `languages` | TEXT[] NOT NULL | `{ro,ru}` — descriptive. |
| `is_published` | BOOLEAN NOT NULL DEFAULT false | Drafts stay invisible. |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

**`languages` describes; it does not offer a choice.** One document contains every language
it is written in. The column drives the "Limbi incluse: RO, RU" label and nothing else — it
never multiplies the price. This was true from 2026-07-17; the earlier per-language pricing
model is gone (the prototype keeps the old selector commented out).

**Price lives here, not on the version.** A price change is not a content change, and
should not require a new document version. Orders snapshot the price anyway.

### `template_versions` — phase 4

The actual `.docx`, versioned. **This table is what makes sold documents reproducible.**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `template_id` | UUID FK → contract_templates | |
| `version` | INT NOT NULL | 1, 2, 3… UNIQUE with template_id. |
| `docx_object_key` | TEXT NOT NULL | Storage key, not a filesystem path. |
| `page_count` | INT | From the rendered PDF. |
| `is_current` | BOOLEAN NOT NULL DEFAULT false | One per template. |
| `uploaded_by` | UUID FK → users | Which admin. |
| `created_at` | TIMESTAMPTZ | |

Rows are **never updated and never deleted.** A lawyer revising wording creates version
N+1; version N stays exactly as it was, because a document sold against it must remain
reproducible years later.

### `payment_cards` — phase 5

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK → users | |
| `provider_token` | TEXT NOT NULL | Opaque token from the acquirer. |
| `brand` | TEXT NOT NULL | `visa`, `mastercard` |
| `last4` | TEXT NOT NULL | For display only. |
| `exp_month` / `exp_year` | INT NOT NULL | |
| `is_default` | BOOLEAN NOT NULL DEFAULT false | |

**We never store a card number, CVV, or expiry-with-PAN.** Only a provider token and the
last four digits for display. Storing a PAN would put this system in PCI-DSS scope, which
is an enormous obligation taken on by accident. The mock provider issues fake tokens so the
shape is identical when a real acquirer arrives.

### `wallet_transactions` — phase 5

The ledger. **There is no balance column anywhere.**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK → users | |
| `amount_bani` | BIGINT NOT NULL CHECK (<> 0) | Signed: `+` credit, `−` debit. |
| `kind` | TEXT NOT NULL CHECK (IN …) | `topup`, `purchase`, `refund`, `adjustment` |
| `order_id` | UUID FK → orders NULL | Set for `purchase`/`refund`. |
| `provider_charge_id` | TEXT NULL | Set for `topup`. |
| `description` | TEXT NOT NULL | Shown in the history UI. |
| `created_at` | TIMESTAMPTZ NOT NULL | `clock_timestamp()`, **not** `now()` — see below. |

Balance is `SELECT COALESCE(SUM(amount_bani), 0) FROM wallet_transactions WHERE user_id = ?`.

**`created_at` defaults to `clock_timestamp()`, and that difference matters.** PostgreSQL's
`now()` returns the *transaction start* time, so every row written in one transaction gets
an identical timestamp. For a ledger that is wrong: the history is ordered by time, and
identical timestamps leave the order to a tiebreak on a random UUID — the same data then
renders in a different order on different requests. `clock_timestamp()` reads the real clock
at insert, so `created_at` means "when this entry happened" rather than "when its
transaction opened". Every other table keeps `now()`, where the distinction is harmless.

**Why derived rather than stored.** A balance column and a transaction list are two records
of the same fact, and two records of one fact drift. When they disagree — and eventually
they do — you cannot tell which is right. Deriving means the history *is* the balance:
always explainable, always reconcilable, and a bug can be diagnosed after the fact instead
of merely observed.

**The cost, stated honestly.** Summing is slower than reading a column, and it makes
concurrency subtle: two simultaneous purchases could each read a sufficient balance and
both succeed, overdrawing the wallet. Deriving does not fix that on its own. The debit path
therefore takes a row lock on the user (`SELECT … FROM users WHERE id = ? FOR UPDATE`)
before computing the balance, which serialises wallet writes per user. At our volume this
is free; at a much larger scale it would need revisiting.

Rows are **never updated and never deleted.** A mistaken transaction is corrected by
writing a compensating one, so the error and its correction both remain visible.

### `carts` and `cart_items` — phase 6

| `carts` | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK → users UNIQUE | One open cart per user. |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

| `cart_items` | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `cart_id` | UUID FK → carts ON DELETE CASCADE | |
| `template_id` | UUID FK → contract_templates | UNIQUE with cart_id. |
| `added_at` | TIMESTAMPTZ | |

**The cart is server-side.** A price the client can edit is not a price.

**No quantity column, and `UNIQUE (cart_id, template_id)`.** Buying the same document twice
is meaningless — you would download the identical file. The constraint makes that
impossible rather than merely discouraged.

**No price snapshot here.** The cart shows the live price; the *order* snapshots it. A cart
that quietly holds last week's price is a bug, not a feature.

### `orders` and `order_items` — phase 6

| `orders` | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK → users | |
| `number` | TEXT UNIQUE NOT NULL | `CT-2026-0184`. Human-facing. |
| `status` | TEXT NOT NULL CHECK (IN …) | `pending`, `paid`, `failed`, `cancelled` |
| `total_bani` | BIGINT NOT NULL CHECK (>= 0) | Sum of items, snapshotted. |
| `payment_method` | TEXT NOT NULL CHECK (IN …) | `wallet`, `card` |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `paid_at` | TIMESTAMPTZ NULL | Null until paid. |

| `order_items` | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `order_id` | UUID FK → orders | |
| `template_id` | UUID FK → contract_templates | Which product. |
| `template_version_id` | UUID FK → template_versions | **Exactly which file.** |
| `name_snapshot` | TEXT NOT NULL | Name at purchase time. |
| `unit_price_bani` | BIGINT NOT NULL | Price at purchase time. |

**`number` is separate from `id`.** The UUID is for machines; `CT-2026-0184` is what a
customer quotes in an email. Making the primary key human-facing would force the two
purposes into one column and leak volume.

**The snapshots are the point.** `name_snapshot` and `unit_price_bani` are deliberate
duplication: a receipt must read the same in 2030 as it did on the day, even after the
template has been renamed twice and repriced three times.

**`template_version_id` is what makes phase 7 possible.** It records the exact file the
customer bought, so the document can be regenerated identically after the template moves on.

### `documents` — phase 7

The generated files.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `order_item_id` | UUID FK → order_items UNIQUE | One document per purchased line. |
| `status` | TEXT NOT NULL CHECK (IN …) | `pending`, `rendering`, `ready`, `failed` |
| `pdf_object_key` | TEXT NULL | Null until ready. |
| `docx_object_key` | TEXT NULL | Null until ready. |
| `page_count` | INT NULL | |
| `render_error` | TEXT NULL | Why it failed, for retrying. |
| `rendered_at` | TIMESTAMPTZ NULL | |

**`status` exists because rendering happens outside the payment transaction.** Document
generation is slow and fails for reasons unrelated to money — a malformed template, a
LibreOffice crash — and none of those may roll back a completed payment. So a paid order
can legitimately have a `pending` or `failed` document. That is a recoverable state: retry
the render. A lost payment is not recoverable, which is why the transaction boundary sits
where it does.

**Object keys, not paths.** Storage sits behind an interface; today a key resolves to a
file in a volume, tomorrow to an S3 object. A column holding `/var/lib/...` would make that
a migration instead of a config change.

## What the database refuses to allow

The constraints worth stating as intent rather than syntax:

- A wallet transaction of exactly zero — `CHECK (amount_bani <> 0)`. It records nothing.
- A negative or zero template price — `CHECK (price_bani > 0)`. We do not give documents away.
- The same document twice in one cart — `UNIQUE (cart_id, template_id)`.
- Two accounts with one email — `UNIQUE (email)`, lowercase on write.
- Two sessions sharing a token — `UNIQUE (token_hash)`.
- Two versions numbered the same — `UNIQUE (template_id, version)`.
- Two documents for one order line — `UNIQUE (order_item_id)`.
- An order line pointing at no specific file — `template_version_id NOT NULL`.

## Indexes

Beyond the primary keys and uniques above:

| Index | Why |
| --- | --- |
| `wallet_transactions (user_id, created_at DESC)` | Every balance sums this, and the history screen pages it. The hottest read in the system. |
| `orders (user_id, created_at DESC)` | Order history. |
| `contract_templates (category_id) WHERE is_published` | Catalog filtering, which only ever sees published rows. |
| `documents (status) WHERE status IN ('pending','failed')` | Finding renders to retry. Partial, because the healthy rows are the overwhelming majority and are never scanned this way. |

## Open questions

Deliberately unresolved, and better answered with real data than guessed at now:

- **VAT.** The design mentions an invoice but no VAT line. Moldovan VAT is 20%, and whether
  prices are inclusive changes what `total_bani` means. Needs an answer from the finance
  side before phase 6.
- **Order numbering.** `CT-2026-0184` implies a per-year sequence. Concurrent checkouts
  make gap-free numbering surprisingly hard; if the accountants can tolerate gaps this is
  trivial, and if not it needs its own table and a lock.
- **Refunds.** The ledger has a `refund` kind, but nothing in the design describes who may
  issue one or what happens to the already-downloaded document.
</content>

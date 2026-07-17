"""Seed the development database.

Loads the categories and templates from the design prototype so the local app
matches the screens the product was designed against.

    docker compose exec backend python -m scripts.seed

Idempotent: safe to run repeatedly. It upserts by slug rather than inserting,
so it will not accumulate duplicates.

**Every template points at the same placeholder .docx.** We have exactly one
sample document — an internal 2FA guide, not a contract — until the legal team
delivers the real templates. So the catalog reads correctly and every preview
shows the same unrelated document. That is expected, and it is why this script
refuses to run outside development.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.documents.renderer import docx_to_pdf, fill_template
from app.integrations.storage.base import Storage
from app.integrations.storage.local import LocalStorage
from app.models.catalog import Category, ContractTemplate, TemplateVersion

PLACEHOLDER_DOCX = Path("tests/fixtures/activare-2fa.docx")
PLACEHOLDER_KEY = "templates/placeholder/activare-2fa.docx"

CATEGORIES = [
    ("servicii", "Servicii & Colaborare", "Prestări servicii, contracte de colaborare, comision.", 1),
    ("imobiliare", "Imobiliare & Chirie", "Închiriere, arendă spații locative și comerciale.", 2),
    ("vanzare", "Vânzare-cumpărare", "Bunuri mobile, imobile, auto și donație.", 3),
    ("munca", "Muncă & HR", "Contracte individuale de muncă, acorduri adiționale.", 4),
    ("confidentialitate", "Confidențialitate", "Acorduri NDA uni- și bilaterale, clauze de neconcurență.", 5),
    ("transport", "Transport & Livrare", "Transport de mărfuri, livrare recurentă, expediție.", 6),
]

# (slug, name, category_slug, price_bani, description)
TEMPLATES = [
    ("prestari-servicii", "Contract de prestări servicii", "servicii", 90000,
     "Reglementează prestarea de servicii între un prestator și un beneficiar, cu obiect, "
     "termene, tarife și modalitate de plată."),
    ("colaborare", "Contract de colaborare", "servicii", 100000,
     "Parteneriat comercial între companii, cu obiective și repartizarea rolurilor."),
    ("inchiriere-imobil", "Contract de închiriere imobil", "imobiliare", 100000,
     "Închiriere de spații locative sau comerciale, cu clauze de plată și întreținere."),
    ("vanzare-cumparare", "Contract de vânzare-cumpărare", "vanzare", 80000,
     "Transfer de proprietate asupra bunurilor mobile sau imobile între părți."),
    ("donatie", "Contract de donație", "vanzare", 80000,
     "Transmiterea gratuită a unui bun, cu condiții și acceptarea donatarului."),
    ("contract-munca", "Contract individual de muncă", "munca", 90000,
     "Angajare conform Codului muncii al RM, cu funcție, salariu și program."),
    ("nda", "Acord de confidențialitate (NDA)", "confidentialitate", 80000,
     "Protejează informația comercială sensibilă între părți în cadrul unei colaborări."),
    ("transport-marfuri", "Contract de transport de mărfuri", "transport", 120000,
     "Transport rutier de mărfuri, cu responsabilități și termene de livrare."),
    ("livrare-produse", "Contract de livrare de produse", "transport", 100000,
     "Furnizarea recurentă de produse, cu cantități, prețuri și condiții de livrare."),
]

LANGUAGES = ["ro", "ru"]


def _upload_placeholder(storage: Storage) -> int:
    """Put the placeholder in storage and return its page count."""
    if not PLACEHOLDER_DOCX.is_file():
        raise SystemExit(f"Placeholder document not found: {PLACEHOLDER_DOCX.resolve()}")

    storage.put(PLACEHOLDER_KEY, PLACEHOLDER_DOCX.read_bytes())

    import tempfile

    from pypdf import PdfReader

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        filled = fill_template(PLACEHOLDER_DOCX, {}, workdir / "filled.docx")
        pdf = docx_to_pdf(filled, workdir)
        return len(PdfReader(str(pdf)).pages)


async def _seed_categories(session: AsyncSession) -> dict[str, Category]:
    by_slug: dict[str, Category] = {}

    for slug, name, description, order in CATEGORIES:
        category = await session.scalar(select(Category).where(Category.slug == slug))
        if category is None:
            category = Category(slug=slug)
            session.add(category)
        category.name = name
        category.description = description
        category.sort_order = order
        by_slug[slug] = category

    await session.flush()
    return by_slug


async def _seed_templates(
    session: AsyncSession, categories: dict[str, Category], page_count: int
) -> int:
    created = 0

    for slug, name, category_slug, price_bani, description in TEMPLATES:
        template = await session.scalar(
            select(ContractTemplate).where(ContractTemplate.slug == slug)
        )
        if template is None:
            template = ContractTemplate(slug=slug)
            session.add(template)
            created += 1

        template.name = name
        template.description = description
        template.category_id = categories[category_slug].id
        template.price_bani = price_bani
        template.languages = LANGUAGES
        template.is_published = True
        await session.flush()

        existing = await session.scalar(
            select(TemplateVersion).where(
                TemplateVersion.template_id == template.id, TemplateVersion.version == 1
            )
        )
        if existing is None:
            session.add(
                TemplateVersion(
                    template_id=template.id,
                    version=1,
                    docx_object_key=PLACEHOLDER_KEY,
                    page_count=page_count,
                    is_current=True,
                )
            )
        else:
            existing.docx_object_key = PLACEHOLDER_KEY
            existing.page_count = page_count

    await session.flush()
    return created


async def main() -> int:
    settings = get_settings()

    # Seed data is fake by construction — placeholder documents, invented
    # prices. Loading it into a real catalog would put nonsense in front of
    # customers, so this refuses rather than trusts the operator.
    if not settings.is_development:
        print(
            f"Refusing to seed: ENVIRONMENT is {settings.environment!r}, not 'development'.",
            file=sys.stderr,
        )
        return 1

    storage = LocalStorage(settings.document_storage_path)

    print("Uploading placeholder document…")
    page_count = _upload_placeholder(storage)
    print(f"  {PLACEHOLDER_KEY} ({page_count} pages)")

    async with SessionFactory() as session:
        categories = await _seed_categories(session)
        created = await _seed_templates(session, categories, page_count)
        await session.commit()

    print(f"\n{len(categories)} categories, {len(TEMPLATES)} templates ({created} new).")
    print(
        "\nNOTE: every template points at the same placeholder document — an internal\n"
        "2FA guide, not a contract. Previews will all show it. Real templates come\n"
        "from the legal team."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

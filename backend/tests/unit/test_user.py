"""Email normalisation.

Pure logic, no database — the unique constraint is only as good as the
normalisation feeding it, so this is worth testing on its own.
"""

import pytest

from app.models.user import normalise_email


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ion@nordconstruct.md", "ion@nordconstruct.md"),
        ("Ion@NordConstruct.md", "ion@nordconstruct.md"),
        ("ION@NORDCONSTRUCT.MD", "ion@nordconstruct.md"),
        ("  ion@nordconstruct.md  ", "ion@nordconstruct.md"),
        ("\tIon@NordConstruct.MD\n", "ion@nordconstruct.md"),
    ],
)
def test_normalisation_is_case_and_whitespace_insensitive(raw: str, expected: str) -> None:
    assert normalise_email(raw) == expected


def test_normalisation_is_idempotent() -> None:
    """Applying it twice must not differ from applying it once.

    Otherwise a value read back and re-saved could stop matching itself.
    """
    once = normalise_email("Ion@NordConstruct.md")

    assert normalise_email(once) == once


def test_provider_specific_rules_are_not_applied() -> None:
    """Dots and plus-addressing are left alone, deliberately.

    Gmail treats ion.popescu@ and ionpopescu@ as one mailbox. Most providers do
    not. Collapsing them would merge two genuinely different people's accounts
    on any provider that disagrees — a much worse failure than allowing one
    person two accounts.
    """
    assert normalise_email("ion.popescu@gmail.com") == "ion.popescu@gmail.com"
    assert normalise_email("ion+contracte@gmail.com") == "ion+contracte@gmail.com"

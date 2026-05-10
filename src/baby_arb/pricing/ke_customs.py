"""KE customs calculation: duty + VAT + IDF + RDL on CIF value."""

from __future__ import annotations

from decimal import Decimal

from baby_arb.pricing.rules import (
    KE_DUTY_RATE,
    KE_IDF_RATE,
    KE_RDL_RATE,
    KE_VAT_RATE,
)


def calculate_ke_customs(cif_kes: Decimal) -> dict[str, Decimal]:
    """Calculate KE customs charges from CIF value in KES.

    Order of calculation matters: VAT is applied to (CIF + duty),
    not just CIF. IDF and RDL are on CIF alone.

    Args:
        cif_kes: Cost + Insurance + Freight in KES.

    Returns:
        Dict with duty, idf, rdl, vat, and total in KES.
    """
    duty = cif_kes * KE_DUTY_RATE
    idf = cif_kes * KE_IDF_RATE
    rdl = cif_kes * KE_RDL_RATE
    vat = (cif_kes + duty) * KE_VAT_RATE

    total = duty + idf + rdl + vat

    return {
        "duty": duty,
        "idf": idf,
        "rdl": rdl,
        "vat": vat,
        "total": total,
    }

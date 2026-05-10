"""SQLite (dev) / Postgres (prod) storage layer.

Status: skeleton for Hermes/Copilot.

Hermes handoff:
    Build src/baby_arb/storage/db.py:
      - SQLModel engine creation from settings.database_url
      - get_session() context manager
    Build src/baby_arb/storage/tables.py:
      - SQLModel tables: briefs, candidates, pricing_verdicts,
        compliance_verdicts, purchases, shipments, sales,
        margin_evaluations
    Build src/baby_arb/storage/repo.py:
      - one repo function per use case
      - save_pricing_verdict(verdict)
      - save_compliance_verdict(verdict)
      - get_completed_sales(since) for Margin Evaluator

The pricing engine and compliance gate are intentionally storage-free.
The orchestrator (CLI or Hermes runner) calls them and decides what
to persist.
"""

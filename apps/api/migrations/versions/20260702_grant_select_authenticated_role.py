"""grant select on rls-protected tables to authenticated

Revision ID: a45b7568fa27
Revises: 2fa42fe6f771
Create Date: 2026-07-02 02:01:51.406551

ADR-027. Card 5's spike found that the baseline migration
(2fa42fe6f771) enables RLS and creates policies on all six tenant-scoped
tables, but never GRANTs the `authenticated` role the base table
privileges RLS policies depend on -- Postgres checks table-level
privileges before it evaluates row-security policies at all, so without
these grants every policy was correctly defined but completely
unreachable (`permission denied for table ...`, never even reaching the
policy).

SELECT only -- all writes to these tables go through the API's
service-role connection, which bypasses RLS/grants entirely by design
(ADR-006). The one legitimate direct-from-browser path using the
`authenticated` role (no API in front of it) is the internal-recipient
dashboard read (BR-12e), which is read-only.

`recipient_tokens` is deliberately excluded, matching Batch 3 Section 2:
no `authenticated`/`anon` role should ever get row access to it, only
the service-role connection touches it.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a45b7568fa27"
down_revision: str | Sequence[str] | None = "2fa42fe6f771"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ["companies", "profiles", "envelopes", "recipients", "fields", "audit_events"]


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA public TO authenticated")
    for table in TABLES:
        op.execute(f"GRANT SELECT ON public.{table} TO authenticated")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"REVOKE SELECT ON public.{table} FROM authenticated")

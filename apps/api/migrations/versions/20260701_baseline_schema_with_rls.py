"""baseline schema with RLS

Revision ID: 2fa42fe6f771
Revises:
Create Date: 2026-07-01 23:18:21.473498

Baseline schema per Deliverable 2, Batch 3 (ER diagram + §2 RLS policy summary).
Tables: companies, profiles, envelopes, recipients, fields, audit_events,
recipient_tokens. RLS enabled on all tenant-scoped tables (ADR-006), with
company_id denormalized onto child tables (ADR-009) so every policy is a
flat, single-column check. `current_user_company_id()` is the shared helper
every non-profiles policy calls.

FK ON DELETE choices aren't specified in Batch 3, so a judgment call: CASCADE
for strict ownership chains (company -> its rows, envelope -> its rows,
recipient -> its rows), RESTRICT for references *into* profiles (owner_id,
linked_profile_id, actor_profile_id) since profiles are soft-deactivated
(the `active` column) rather than hard-deleted anywhere in the product spec.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2fa42fe6f771"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    # -- companies --------------------------------------------------------
    op.create_table(
        "companies",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),
    )

    # -- profiles (id = auth.users.id) -------------------------------------
    op.create_table(
        "profiles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.CheckConstraint("role IN ('admin', 'sender')", name="ck_profiles_role"),
    )
    op.create_index("idx_profiles_company_id", "profiles", ["company_id"])

    # -- envelopes ----------------------------------------------------------
    op.create_table(
        "envelopes",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("signing_order", sa.Text(), nullable=False),
        sa.Column("original_file_key", sa.Text(), nullable=True),
        sa.Column("original_file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("completed_file_key", sa.Text(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("sent_at", TIMESTAMPTZ, nullable=True),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("voided_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["profiles.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'partial', 'declined', 'completed', 'voided')",
            name="ck_envelopes_status",
        ),
        sa.CheckConstraint(
            "signing_order IN ('sequential', 'parallel')", name="ck_envelopes_signing_order"
        ),
    )
    op.create_index("idx_envelopes_company_id", "envelopes", ["company_id"])
    op.create_index("idx_envelopes_owner_id", "envelopes", ["owner_id"])

    # -- recipients -----------------------------------------------------------
    op.create_table(
        "recipients",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("envelope_id", UUID, nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("linked_profile_id", UUID, nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("envelope_role", sa.Text(), nullable=False),
        sa.Column("signing_order_index", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("decline_comment", sa.Text(), nullable=True),
        sa.Column("signed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("declined_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["envelope_id"], ["envelopes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_profile_id"], ["profiles.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("envelope_role IN ('signer', 'cc')", name="ck_recipients_envelope_role"),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'viewed', 'signed', 'declined')",
            name="ck_recipients_status",
        ),
    )
    op.create_index("idx_recipients_envelope_id", "recipients", ["envelope_id"])
    op.create_index("idx_recipients_company_id", "recipients", ["company_id"])
    op.create_index("idx_recipients_linked_profile_id", "recipients", ["linked_profile_id"])

    # -- fields ---------------------------------------------------------------
    op.create_table(
        "fields",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("recipient_id", UUID, nullable=False),
        sa.Column("envelope_id", UUID, nullable=False),
        sa.Column("field_type", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("x", sa.Numeric(), nullable=False),
        sa.Column("y", sa.Numeric(), nullable=False),
        sa.Column("width", sa.Numeric(), nullable=False),
        sa.Column("height", sa.Numeric(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["recipient_id"], ["recipients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["envelope_id"], ["envelopes.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "field_type IN ('signature', 'date', 'text')", name="ck_fields_field_type"
        ),
    )
    op.create_index("idx_fields_recipient_id", "fields", ["recipient_id"])
    op.create_index("idx_fields_envelope_id", "fields", ["envelope_id"])

    # -- audit_events -----------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("envelope_id", UUID, nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_profile_id", UUID, nullable=True),
        sa.Column("actor_email", sa.Text(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("occurred_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["envelope_id"], ["envelopes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_profile_id"], ["profiles.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "actor_type IN ('user', 'recipient', 'system')", name="ck_audit_events_actor_type"
        ),
    )
    op.create_index("idx_audit_events_envelope_id", "audit_events", ["envelope_id"])
    op.create_index("idx_audit_events_company_id", "audit_events", ["company_id"])

    # -- recipient_tokens -------------------------------------------------------
    op.create_table(
        "recipient_tokens",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("recipient_id", UUID, nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("token_type", sa.Text(), nullable=False),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=True),
        sa.Column("used_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["recipient_id"], ["recipients.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "token_type IN ('signing', 'download')", name="ck_recipient_tokens_token_type"
        ),
    )
    op.create_index("idx_recipient_tokens_recipient_id", "recipient_tokens", ["recipient_id"])
    # Hot path: every signing/download request looks up a token by its hash (Batch 4).
    op.create_index("idx_recipient_tokens_token_hash", "recipient_tokens", ["token_hash"])

    # -- current_user_company_id() helper (Batch 3 §2) ---------------------------
    # SECURITY DEFINER + fixed search_path: standard Supabase RLS-helper pattern —
    # avoids re-evaluating the calling policy against this lookup, and pins the
    # schema search path so the function can't be hijacked by a session-local
    # search_path change (a known SECURITY DEFINER footgun).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION current_user_company_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT company_id FROM profiles WHERE id = auth.uid();
        $$;
        """
    )

    # -- RLS (Batch 3 §2, ADR-006) -------------------------------------------------
    op.execute("ALTER TABLE companies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE envelopes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recipients ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE fields ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recipient_tokens ENABLE ROW LEVEL SECURITY")

    # profiles: literal subquery, not the helper (the helper itself queries
    # profiles — using it here would be circular in a way that's harder to
    # read, even though Postgres would evaluate it fine either way).
    op.execute(
        """
        CREATE POLICY profiles_company_isolation ON profiles
        FOR ALL
        USING (company_id = (SELECT company_id FROM profiles WHERE id = auth.uid()))
        WITH CHECK (company_id = (SELECT company_id FROM profiles WHERE id = auth.uid()))
        """
    )

    # companies: a user may only see their own company row (readable via the
    # same helper; Batch 3's table doesn't list `companies` explicitly since
    # it's the tenant root, but leaving it unpolicied while RLS is enabled
    # would deny all access — this is the natural extension of ADR-006 to
    # the one table the summary table omitted).
    op.execute(
        """
        CREATE POLICY companies_self_isolation ON companies
        FOR ALL
        USING (id = current_user_company_id())
        WITH CHECK (id = current_user_company_id())
        """
    )

    op.execute(
        """
        CREATE POLICY envelopes_company_isolation ON envelopes
        FOR ALL
        USING (company_id = current_user_company_id())
        WITH CHECK (company_id = current_user_company_id())
        """
    )

    op.execute(
        """
        CREATE POLICY recipients_company_isolation ON recipients
        FOR ALL
        USING (
            company_id = current_user_company_id()
            OR linked_profile_id = auth.uid()
        )
        WITH CHECK (
            company_id = current_user_company_id()
            OR linked_profile_id = auth.uid()
        )
        """
    )

    op.execute(
        """
        CREATE POLICY fields_company_isolation ON fields
        FOR ALL
        USING (
            EXISTS (
                SELECT 1 FROM envelopes
                WHERE envelopes.id = fields.envelope_id
                AND envelopes.company_id = current_user_company_id()
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM envelopes
                WHERE envelopes.id = fields.envelope_id
                AND envelopes.company_id = current_user_company_id()
            )
        )
        """
    )

    op.execute(
        """
        CREATE POLICY audit_events_company_isolation ON audit_events
        FOR ALL
        USING (company_id = current_user_company_id())
        WITH CHECK (company_id = current_user_company_id())
        """
    )

    # recipient_tokens: RLS enabled above, deliberately zero policies — per
    # Batch 3 §2, no authenticated/anon role gets row access at all; only the
    # service-role connection (which bypasses RLS) ever touches this table.


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_events_company_isolation ON audit_events")
    op.execute("DROP POLICY IF EXISTS fields_company_isolation ON fields")
    op.execute("DROP POLICY IF EXISTS recipients_company_isolation ON recipients")
    op.execute("DROP POLICY IF EXISTS envelopes_company_isolation ON envelopes")
    op.execute("DROP POLICY IF EXISTS companies_self_isolation ON companies")
    op.execute("DROP POLICY IF EXISTS profiles_company_isolation ON profiles")

    op.execute("DROP FUNCTION IF EXISTS current_user_company_id()")

    op.drop_table("recipient_tokens")
    op.drop_table("audit_events")
    op.drop_table("fields")
    op.drop_table("recipients")
    op.drop_table("envelopes")
    op.drop_table("profiles")
    op.drop_table("companies")

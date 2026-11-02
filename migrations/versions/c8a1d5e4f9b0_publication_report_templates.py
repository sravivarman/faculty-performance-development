"""Store reusable Publications report-builder layouts without duplicating records."""

from alembic import op
import sqlalchemy as sa


revision = "c8a1d5e4f9b0"
down_revision = "a4c8f7e2d6b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "publication_report_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("publication_report_templates")

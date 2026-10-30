"""Add nullable category-specific funding summary amounts without data conversion.

Existing submitted records may contain an ambiguous historical value in
``sanctioned_amount``.  This revision deliberately does not copy, clear, or
reinterpret that data; reconciliation remains an explicit coordinator action.
"""

from alembic import op
import sqlalchemy as sa


revision = "a4c8f7e2d6b1"
down_revision = "f14e9c2a7b35"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("funding_projects") as batch:
        batch.add_column(sa.Column("proposed_amount", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("contract_amount", sa.Numeric(14, 2), nullable=True))
        batch.create_check_constraint(
            "funding_project_proposed_amount_valid",
            "proposed_amount IS NULL OR proposed_amount >= 0",
        )
        batch.create_check_constraint(
            "funding_project_contract_amount_valid",
            "contract_amount IS NULL OR contract_amount >= 0",
        )


def downgrade():
    bind = op.get_bind()
    populated = bind.execute(sa.text(
        "SELECT COUNT(*) FROM funding_projects "
        "WHERE proposed_amount IS NOT NULL OR contract_amount IS NOT NULL"
    )).scalar_one()
    if populated:
        raise RuntimeError(
            "Cannot downgrade while category-specific financial amounts exist; "
            "export or reconcile them first to avoid data loss."
        )

    with op.batch_alter_table("funding_projects") as batch:
        batch.drop_constraint("funding_project_contract_amount_valid", type_="check")
        batch.drop_constraint("funding_project_proposed_amount_valid", type_="check")
        batch.drop_column("contract_amount")
        batch.drop_column("proposed_amount")

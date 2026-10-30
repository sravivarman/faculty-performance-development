"""Permit multiple PI-level funding investigators and preserve agency terminology."""

from alembic import op
import sqlalchemy as sa


revision = "e2b7c4d9a613"
down_revision = "d9e6f1a4c782"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("uq_funding_project_pi", table_name="funding_project_faculty")
    with op.batch_alter_table("funding_project_faculty") as batch:
        batch.drop_constraint("funding_project_faculty_role_valid", type_="check")
        batch.add_column(sa.Column("agency_role_label", sa.String(100), nullable=True))
        batch.add_column(sa.Column("is_designated_lead", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch.create_check_constraint(
            "funding_project_faculty_role_valid",
            "role IN ('LEAD_PI','PI','CO_PI','CO_INVESTIGATOR','ADMIN_PI','BENEFICIARY')",
        )
    op.create_index(
        "uq_funding_project_designated_lead",
        "funding_project_faculty",
        ["funding_project_id"],
        unique=True,
        sqlite_where=sa.text("is_designated_lead = 1"),
    )


def downgrade():
    bind = op.get_bind()
    incompatible = bind.execute(sa.text(
        "SELECT COUNT(*) FROM funding_project_faculty "
        "WHERE role NOT IN ('PI','CO_PI','BENEFICIARY') "
        "OR agency_role_label IS NOT NULL OR is_designated_lead = 1"
    )).scalar_one()
    multiple_pis = bind.execute(sa.text(
        "SELECT COUNT(*) FROM (SELECT funding_project_id FROM funding_project_faculty "
        "WHERE role = 'PI' GROUP BY funding_project_id HAVING COUNT(*) > 1)"
    )).scalar_one()
    if incompatible or multiple_pis:
        raise RuntimeError("Cannot downgrade while records use flexible investigator roles, agency labels, lead designations, or multiple PIs.")

    op.drop_index("uq_funding_project_designated_lead", table_name="funding_project_faculty")
    with op.batch_alter_table("funding_project_faculty") as batch:
        batch.drop_constraint("funding_project_faculty_role_valid", type_="check")
        batch.drop_column("is_designated_lead")
        batch.drop_column("agency_role_label")
        batch.create_check_constraint("funding_project_faculty_role_valid", "role IN ('PI','CO_PI','BENEFICIARY')")
    op.create_index("uq_funding_project_pi", "funding_project_faculty", ["funding_project_id"], unique=True, sqlite_where=sa.text("role = 'PI'"))

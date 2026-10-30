"""Restrict new funding investigator choices while preserving legacy roles."""

from alembic import op
import sqlalchemy as sa


revision = "f14e9c2a7b35"
down_revision = "e2b7c4d9a613"
branch_labels = None
depends_on = None


def upgrade():
    # PI and CO_INVESTIGATOR are retained only so historical associations can
    # be read and edited without data loss. The API exposes five active roles
    # for new assignments and rejects attempts to create either legacy value.
    with op.batch_alter_table("funding_project_faculty") as batch:
        batch.drop_constraint("funding_project_faculty_role_valid", type_="check")
        batch.create_check_constraint(
            "funding_project_faculty_role_valid",
            "role IN ('LEAD_PI','MEMBER_PI','CO_PI','ADMIN_PI','BENEFICIARY','PI','CO_INVESTIGATOR')",
        )


def downgrade():
    bind = op.get_bind()
    member_pis = bind.execute(sa.text(
        "SELECT COUNT(*) FROM funding_project_faculty WHERE role = 'MEMBER_PI'"
    )).scalar_one()
    if member_pis:
        raise RuntimeError("Cannot downgrade while MEMBER_PI associations exist.")

    with op.batch_alter_table("funding_project_faculty") as batch:
        batch.drop_constraint("funding_project_faculty_role_valid", type_="check")
        batch.create_check_constraint(
            "funding_project_faculty_role_valid",
            "role IN ('LEAD_PI','PI','CO_PI','CO_INVESTIGATOR','ADMIN_PI','BENEFICIARY')",
        )

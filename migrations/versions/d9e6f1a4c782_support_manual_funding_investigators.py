"""Allow manual PI and Co-PI snapshots alongside Faculty Master investigators."""

from alembic import op
import sqlalchemy as sa


revision = "d9e6f1a4c782"
down_revision = "c4d1e8a7b9f2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("funding_project_faculty") as batch:
        batch.alter_column("faculty_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("investigator_name", sa.String(500), nullable=True))
        batch.add_column(sa.Column("department_name", sa.String(250), nullable=True))
        batch.add_column(sa.Column("institution_name", sa.String(500), nullable=True))
        batch.add_column(sa.Column("affiliation_type", sa.String(30), nullable=False, server_default="FACULTY_MASTER"))
        batch.add_column(sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))
        batch.create_check_constraint(
            "funding_project_investigator_identity",
            "faculty_id IS NOT NULL OR (investigator_name IS NOT NULL AND length(trim(investigator_name)) > 0)",
        )
        batch.create_check_constraint(
            "funding_project_investigator_affiliation_valid",
            "affiliation_type IN ('FACULTY_MASTER','MANUAL')",
        )
    op.execute("UPDATE funding_project_faculty SET display_order = id WHERE display_order = 0")


def downgrade():
    bind = op.get_bind()
    manual = bind.execute(sa.text("SELECT COUNT(*) FROM funding_project_faculty WHERE faculty_id IS NULL")).scalar_one()
    if manual:
        raise RuntimeError("Cannot downgrade while manually entered funding investigators exist.")
    with op.batch_alter_table("funding_project_faculty") as batch:
        batch.drop_constraint("funding_project_investigator_affiliation_valid", type_="check")
        batch.drop_constraint("funding_project_investigator_identity", type_="check")
        batch.drop_column("display_order")
        batch.drop_column("affiliation_type")
        batch.drop_column("institution_name")
        batch.drop_column("department_name")
        batch.drop_column("investigator_name")
        batch.alter_column("faculty_id", existing_type=sa.Integer(), nullable=False)

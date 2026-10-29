"""Remove the unused PROFESSIONAL_CERTIFICATION category constraint value."""

from alembic import op


revision = "c7d8e9f0a1b2"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("certifications") as batch:
        batch.drop_constraint("certification_category_valid", type_="check")
        batch.create_check_constraint(
            "certification_category_valid",
            "category IN ('NPTEL_SWAYAM','MOOC','OTHER')",
        )


def downgrade():
    with op.batch_alter_table("certifications") as batch:
        batch.drop_constraint("certification_category_valid", type_="check")
        batch.create_check_constraint(
            "certification_category_valid",
            "category IN ('NPTEL_SWAYAM','MOOC','PROFESSIONAL_CERTIFICATION','OTHER')",
        )

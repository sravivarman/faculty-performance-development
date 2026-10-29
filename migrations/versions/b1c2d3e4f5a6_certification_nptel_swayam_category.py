"""Allow NPTEL / SWAYAM certifications without rewriting legacy categories."""

from alembic import op


revision = "b1c2d3e4f5a6"
down_revision = "d81f4b6c2201"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("certifications") as batch:
        batch.drop_constraint("certification_category_valid", type_="check")
        batch.create_check_constraint(
            "certification_category_valid",
            "category IN ('NPTEL_SWAYAM','MOOC','PROFESSIONAL_CERTIFICATION','OTHER')",
        )


def downgrade():
    raise RuntimeError("Downgrade intentionally disabled: NPTEL_SWAYAM rows cannot satisfy the historical constraint without data loss.")

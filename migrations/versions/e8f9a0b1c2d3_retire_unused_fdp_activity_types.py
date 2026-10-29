"""Retire unused FDP activity types from the active constraint."""

from alembic import op


revision = "e8f9a0b1c2d3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("fdp_activities") as batch:
        batch.drop_constraint("fdp_activity_type_valid", type_="check")
        batch.create_check_constraint(
            "fdp_activity_type_valid",
            "activity_type IN ('FDP','STTP','WORKSHOP','WEBINAR','SEMINAR','INTERNSHIP','INDUSTRIAL_TRAINING')",
        )


def downgrade():
    with op.batch_alter_table("fdp_activities") as batch:
        batch.drop_constraint("fdp_activity_type_valid", type_="check")
        batch.create_check_constraint(
            "fdp_activity_type_valid",
            "activity_type IN ('FDP','STTP','WORKSHOP','WEBINAR','SEMINAR','INTERNSHIP','INDUSTRIAL_TRAINING','PROFESSIONAL_TRAINING','INDUSTRY_COLLABORATION','OTHER')",
        )

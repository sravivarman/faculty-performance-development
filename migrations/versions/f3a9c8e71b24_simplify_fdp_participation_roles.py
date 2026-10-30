"""Restrict FDP participant roles to attendee, resource person, and coordinator."""

from alembic import op
import sqlalchemy as sa


revision = "f3a9c8e71b24"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    retired = bind.execute(
        sa.text("SELECT role, COUNT(*) FROM fdp_participants "
                "WHERE role IN ('ORGANIZER','CONDUCTOR','PARTICIPANT','TRAINEE','COLLABORATOR','OTHER') "
                "GROUP BY role ORDER BY role")
    ).all()
    if retired:
        raise RuntimeError(
            "Cannot retire FDP participation roles while associations still use them: "
            + ", ".join(f"{role} ({count})" for role, count in retired)
        )

    with op.batch_alter_table("fdp_participants") as batch:
        batch.drop_constraint("fdp_participant_role_valid", type_="check")
        batch.create_check_constraint(
            "fdp_participant_role_valid",
            "role IN ('ATTENDEE','RESOURCE_PERSON','COORDINATOR')",
        )


def downgrade():
    with op.batch_alter_table("fdp_participants") as batch:
        batch.drop_constraint("fdp_participant_role_valid", type_="check")
        batch.create_check_constraint(
            "fdp_participant_role_valid",
            "role IN ('ATTENDEE','RESOURCE_PERSON','ORGANIZER','CONDUCTOR','PARTICIPANT','TRAINEE','COLLABORATOR','OTHER')",
        )

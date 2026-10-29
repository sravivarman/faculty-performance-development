"""Add coordinator-managed Faculty Development Activities and Certifications."""
from alembic import op
import sqlalchemy as sa

revision = "d81f4b6c2201"
down_revision = "a03d26e71002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("fdp_activities",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.Text(), nullable=False),
        sa.Column("activity_type", sa.String(40), nullable=False), sa.Column("organizing_institution", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date()),
        sa.Column("duration_value", sa.Numeric(10, 2), nullable=False), sa.Column("duration_unit", sa.String(20), nullable=False),
        sa.Column("location", sa.Text()), sa.Column("mode", sa.String(20)), sa.Column("description", sa.Text()), sa.Column("source_url", sa.Text()),
        sa.Column("outcomes", sa.Text()), sa.Column("internal_notes", sa.Text()), sa.Column("attendance_count", sa.Integer()), sa.Column("company_location", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("activity_type IN ('FDP','STTP','WORKSHOP','WEBINAR','SEMINAR','INTERNSHIP','INDUSTRIAL_TRAINING','PROFESSIONAL_TRAINING','INDUSTRY_COLLABORATION','OTHER')", name="fdp_activity_type_valid"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="fdp_activity_dates_valid"), sa.CheckConstraint("duration_value > 0", name="fdp_activity_duration_valid"),
        sa.CheckConstraint("duration_unit IN ('HOURS','DAYS','WEEKS','MONTHS')", name="fdp_activity_duration_unit_valid"), sa.CheckConstraint("mode IS NULL OR mode IN ('PHYSICAL','ONLINE','HYBRID')", name="fdp_activity_mode_valid"), sa.CheckConstraint("attendance_count IS NULL OR attendance_count >= 0", name="fdp_activity_attendance_valid"))
    op.create_index("ix_fdp_activities_activity_type", "fdp_activities", ["activity_type"]); op.create_index("ix_fdp_activities_start_date", "fdp_activities", ["start_date"])
    op.create_table("fdp_participants", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("activity_id", sa.Integer(), sa.ForeignKey("fdp_activities.id", ondelete="CASCADE"), nullable=False), sa.Column("faculty_id", sa.Integer(), sa.ForeignKey("faculty.id"), nullable=False), sa.Column("role", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("activity_id", "faculty_id", "role", name="uq_fdp_participant_role"), sa.CheckConstraint("role IN ('ATTENDEE','RESOURCE_PERSON','ORGANIZER','CONDUCTOR','PARTICIPANT','TRAINEE','COLLABORATOR','OTHER')", name="fdp_participant_role_valid"))
    op.create_index("ix_fdp_participants_activity_id", "fdp_participants", ["activity_id"]); op.create_index("ix_fdp_participants_faculty_id", "fdp_participants", ["faculty_id"])
    op.create_table("fdp_speakers", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("activity_id", sa.Integer(), sa.ForeignKey("fdp_activities.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.Text(), nullable=False), sa.Column("designation", sa.Text()), sa.Column("organization", sa.Text()), sa.Column("location_or_contact", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("fdp_change_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("activity_id", sa.Integer(), sa.ForeignKey("fdp_activities.id"), nullable=False), sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("action", sa.String(80), nullable=False), sa.Column("changes", sa.JSON(), nullable=False))
    op.create_table("certifications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("faculty_id", sa.Integer(), sa.ForeignKey("faculty.id"), nullable=False), sa.Column("name", sa.Text(), nullable=False), sa.Column("category", sa.String(30), nullable=False), sa.Column("provider", sa.Text(), nullable=False), sa.Column("course_url", sa.Text()), sa.Column("credential_id", sa.String(250)), sa.Column("issue_date", sa.Date()), sa.Column("completion_date", sa.Date()), sa.Column("expiry_date", sa.Date()), sa.Column("grade_score", sa.String(100)), sa.Column("grade_scale", sa.String(250)), sa.Column("status", sa.String(30), nullable=False), sa.Column("notes", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("category IN ('MOOC','PROFESSIONAL_CERTIFICATION','OTHER')", name="certification_category_valid"), sa.CheckConstraint("status IN ('COMPLETED','IN_PROGRESS')", name="certification_status_valid"), sa.CheckConstraint("expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date", name="certification_expiry_valid"), sa.CheckConstraint("status != 'COMPLETED' OR completion_date IS NOT NULL", name="certification_completed_date_required"), sa.UniqueConstraint("faculty_id", "name", "provider", "credential_id", "completion_date", name="uq_certification_identity"))
    for col in ("faculty_id", "category", "status", "issue_date", "completion_date", "expiry_date"): op.create_index(f"ix_certifications_{col}", "certifications", [col])
    op.create_table("certification_change_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("certification_id", sa.Integer(), sa.ForeignKey("certifications.id"), nullable=False), sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("action", sa.String(80), nullable=False), sa.Column("changes", sa.JSON(), nullable=False))
    with op.batch_alter_table("evidence_files") as batch:
        batch.add_column(sa.Column("fdp_activity_id", sa.Integer(), sa.ForeignKey("fdp_activities.id", ondelete="CASCADE", name="fk_evidence_fdp_activity")))
        batch.add_column(sa.Column("certification_id", sa.Integer(), sa.ForeignKey("certifications.id", ondelete="CASCADE", name="fk_evidence_certification")))
        batch.drop_constraint("one_evidence_owner", type_="check")
        batch.create_check_constraint("one_evidence_owner", "(publication_id IS NOT NULL) + (patent_id IS NOT NULL) + (book_record_id IS NOT NULL) + (fdp_activity_id IS NOT NULL) + (certification_id IS NOT NULL) = 1")
        batch.create_index("ix_evidence_files_fdp_activity_id", ["fdp_activity_id"])
        batch.create_index("ix_evidence_files_certification_id", ["certification_id"])


def downgrade():
    raise RuntimeError("Downgrade intentionally disabled: preserve production evidence ownership and historical records.")

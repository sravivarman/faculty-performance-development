"""Add shared funding-project records for sponsored research, consultancy and seed grants."""

from alembic import op
import sqlalchemy as sa


revision = "c4d1e8a7b9f2"
down_revision = "f3a9c8e71b24"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "funding_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("department", sa.String(250), nullable=False),
        sa.Column("funding_agency", sa.Text()),
        sa.Column("proposal_submission_date", sa.Date()),
        sa.Column("sanction_date", sa.Date()),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("sanctioned_amount", sa.Numeric(14, 2)),
        sa.Column("amount_received", sa.Numeric(14, 2)),
        sa.Column("amount_utilized", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("reference_number", sa.String(250)),
        sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("description", sa.Text()),
        sa.Column("outcomes", sa.Text()),
        sa.Column("deliverables", sa.Text()),
        sa.Column("completion_details", sa.Text()),
        sa.Column("internal_notes", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("category IN ('SPONSORED_RESEARCH','CONSULTANCY','INTERNAL_GRANT')", name="funding_project_category_valid"),
        sa.CheckConstraint("status IN ('DRAFT','SUBMITTED','UNDER_REVIEW','SANCTIONED','ONGOING','COMPLETED','REJECTED','WITHDRAWN')", name="funding_project_status_valid"),
        sa.CheckConstraint("currency = 'INR'", name="funding_project_currency_inr"),
        sa.CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="funding_project_dates_valid"),
        sa.CheckConstraint("sanctioned_amount IS NULL OR sanctioned_amount >= 0", name="funding_project_sanctioned_amount_valid"),
        sa.CheckConstraint("amount_received IS NULL OR amount_received >= 0", name="funding_project_received_amount_valid"),
        sa.CheckConstraint("amount_utilized IS NULL OR amount_utilized >= 0", name="funding_project_utilized_amount_valid"),
    )
    for column in ("category", "proposal_submission_date", "sanction_date", "start_date", "status", "is_active"):
        op.create_index(f"ix_funding_projects_{column}", "funding_projects", [column])

    op.create_table(
        "funding_project_faculty",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("funding_project_id", sa.Integer(), sa.ForeignKey("funding_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("faculty_id", sa.Integer(), sa.ForeignKey("faculty.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("funding_project_id", "faculty_id", "role", name="uq_funding_project_faculty_role"),
        sa.CheckConstraint("role IN ('PI','CO_PI','BENEFICIARY')", name="funding_project_faculty_role_valid"),
    )
    op.create_index("ix_funding_project_faculty_funding_project_id", "funding_project_faculty", ["funding_project_id"])
    op.create_index("ix_funding_project_faculty_faculty_id", "funding_project_faculty", ["faculty_id"])
    op.create_index("uq_funding_project_pi", "funding_project_faculty", ["funding_project_id"], unique=True, sqlite_where=sa.text("role = 'PI'"))

    op.create_table(
        "funding_project_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("funding_project_id", sa.Integer(), sa.ForeignKey("funding_projects.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
    )
    op.create_index("ix_funding_project_change_logs_funding_project_id", "funding_project_change_logs", ["funding_project_id"])

    with op.batch_alter_table("evidence_files") as batch:
        batch.add_column(sa.Column("funding_project_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_evidence_files_funding_project", "funding_projects", ["funding_project_id"], ["id"], ondelete="CASCADE")
        batch.drop_constraint("one_evidence_owner", type_="check")
        batch.create_check_constraint(
            "one_evidence_owner",
            "(publication_id IS NOT NULL) + (patent_id IS NOT NULL) + (book_record_id IS NOT NULL) + (fdp_activity_id IS NOT NULL) + (certification_id IS NOT NULL) + (funding_project_id IS NOT NULL) = 1",
        )
    op.create_index("ix_evidence_files_funding_project_id", "evidence_files", ["funding_project_id"])


def downgrade():
    bind = op.get_bind()
    populated = sum(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in (
        "funding_projects", "funding_project_faculty", "funding_project_change_logs",
    ))
    evidence = bind.execute(sa.text("SELECT COUNT(*) FROM evidence_files WHERE funding_project_id IS NOT NULL")).scalar_one()
    if populated or evidence:
        raise RuntimeError("Cannot downgrade funding-project schema while funding records or their evidence exist.")

    op.drop_index("ix_evidence_files_funding_project_id", table_name="evidence_files")
    with op.batch_alter_table("evidence_files") as batch:
        batch.drop_constraint("one_evidence_owner", type_="check")
        batch.drop_constraint("fk_evidence_files_funding_project", type_="foreignkey")
        batch.drop_column("funding_project_id")
        batch.create_check_constraint(
            "one_evidence_owner",
            "(publication_id IS NOT NULL) + (patent_id IS NOT NULL) + (book_record_id IS NOT NULL) + (fdp_activity_id IS NOT NULL) + (certification_id IS NOT NULL) = 1",
        )

    op.drop_index("ix_funding_project_change_logs_funding_project_id", table_name="funding_project_change_logs")
    op.drop_table("funding_project_change_logs")
    op.drop_index("uq_funding_project_pi", table_name="funding_project_faculty")
    op.drop_index("ix_funding_project_faculty_faculty_id", table_name="funding_project_faculty")
    op.drop_index("ix_funding_project_faculty_funding_project_id", table_name="funding_project_faculty")
    op.drop_table("funding_project_faculty")
    for column in ("is_active", "status", "start_date", "sanction_date", "proposal_submission_date", "category"):
        op.drop_index(f"ix_funding_projects_{column}", table_name="funding_projects")
    op.drop_table("funding_projects")

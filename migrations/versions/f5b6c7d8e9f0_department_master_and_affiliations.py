"""Add the additive institution-wide Department foundation.

The data backfill deliberately records legacy EEE memberships with an unknown
start date.  It never claims the upgrade timestamp was a Faculty member's
actual joining date.
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "f5b6c7d8e9f0"
down_revision = "c8a1d5e4f9b0"
branch_labels = None
depends_on = None


def upgrade():
    now = datetime.now(timezone.utc)
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_departments_code", "departments", ["code"], unique=True)

    bind = op.get_bind()
    eee_id = bind.execute(sa.text("SELECT id FROM departments WHERE code = 'EEE'")).scalar()
    if eee_id is None:
        bind.execute(
            sa.text("INSERT INTO departments (code, name, is_active, created_at, updated_at) VALUES (:code, :name, :active, :created, :updated)"),
            {"code": "EEE", "name": "Electrical and Electronics Engineering", "active": True, "created": now, "updated": now},
        )
        eee_id = bind.execute(sa.text("SELECT id FROM departments WHERE code = 'EEE'")).scalar_one()

    op.create_table(
        "faculty_department_affiliations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("faculty_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="MANUAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("effective_from IS NULL OR effective_to IS NULL OR effective_to >= effective_from", name="faculty_department_affiliation_dates_valid"),
        sa.CheckConstraint("source IN ('MIGRATION_BASELINE','MANUAL_TRANSFER','MANUAL')", name="faculty_department_affiliation_source_valid"),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("faculty_id", "department_id", "effective_from", name="uq_faculty_department_affiliation_start"),
    )
    op.create_index("ix_faculty_department_affiliations_faculty_id", "faculty_department_affiliations", ["faculty_id"])
    op.create_index("ix_faculty_department_affiliations_department_id", "faculty_department_affiliations", ["department_id"])
    op.create_index(
        "uq_faculty_current_primary_department",
        "faculty_department_affiliations",
        ["faculty_id"],
        unique=True,
        sqlite_where=sa.text("is_primary = 1 AND effective_to IS NULL"),
        postgresql_where=sa.text("is_primary = true AND effective_to IS NULL"),
    )

    # A null effective_from is intentional provenance: these pre-existing EEE
    # memberships are known to exist, but their true start date is unknown.
    bind.execute(
        sa.text(
            "INSERT INTO faculty_department_affiliations "
            "(faculty_id, department_id, effective_from, effective_to, is_primary, source, created_at, updated_at) "
            "SELECT f.id, :department_id, NULL, NULL, 1, 'MIGRATION_BASELINE', :created, :updated "
            "FROM faculty f WHERE NOT EXISTS ("
            "SELECT 1 FROM faculty_department_affiliations a "
            "WHERE a.faculty_id = f.id AND a.is_primary = 1 AND a.effective_to IS NULL)"
        ),
        {"department_id": eee_id, "created": now, "updated": now},
    )

    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_students_department", "departments", ["department_id"], ["id"])
        batch.create_index("ix_students_department_id", ["department_id"], unique=False)
    bind.execute(sa.text("UPDATE students SET department_id = :department_id WHERE department_id IS NULL"), {"department_id": eee_id})


def downgrade():
    bind = op.get_bind()
    eee_id = bind.execute(sa.text("SELECT id FROM departments WHERE code = 'EEE'")).scalar()
    if eee_id is None:
        raise RuntimeError("Cannot safely downgrade: the baseline EEE Department is missing.")
    non_baseline = bind.execute(sa.text(
        "SELECT COUNT(*) FROM faculty_department_affiliations "
        "WHERE department_id != :eee OR source != 'MIGRATION_BASELINE' OR effective_from IS NOT NULL OR effective_to IS NOT NULL"
    ), {"eee": eee_id}).scalar_one()
    non_eee_students = bind.execute(sa.text("SELECT COUNT(*) FROM students WHERE department_id != :eee"), {"eee": eee_id}).scalar_one()
    other_departments = bind.execute(sa.text("SELECT COUNT(*) FROM departments WHERE id != :eee"), {"eee": eee_id}).scalar_one()
    if non_baseline or non_eee_students or other_departments:
        raise RuntimeError("Cannot safely downgrade after Department data beyond the EEE migration baseline has been created.")

    with op.batch_alter_table("students") as batch:
        batch.drop_index("ix_students_department_id")
        batch.drop_constraint("fk_students_department", type_="foreignkey")
        batch.drop_column("department_id")
    op.drop_index("uq_faculty_current_primary_department", table_name="faculty_department_affiliations")
    op.drop_index("ix_faculty_department_affiliations_department_id", table_name="faculty_department_affiliations")
    op.drop_index("ix_faculty_department_affiliations_faculty_id", table_name="faculty_department_affiliations")
    op.drop_table("faculty_department_affiliations")
    op.drop_index("ix_departments_code", table_name="departments")
    op.drop_table("departments")

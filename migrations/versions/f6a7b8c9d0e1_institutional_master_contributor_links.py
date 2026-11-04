"""Permit linked VCE contributors from any Department.

The existing affiliation scope values are retained for compatibility.  This
revision only expands the identity checks so ``SAME_INSTITUTION_OTHER_DEPARTMENT``
may retain a stable Faculty or Student Master reference.  It does not rewrite
legacy ``CURRENT_DEPARTMENT`` rows or infer historical Department data.
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "f5b6c7d8e9f0"
branch_labels = None
depends_on = None


IDENTITY = "(faculty_id IS NULL OR (person_type='FACULTY' AND institution_scope IN ('CURRENT_DEPARTMENT','SAME_INSTITUTION_OTHER_DEPARTMENT') AND student_id IS NULL)) AND (student_id IS NULL OR (person_type='STUDENT' AND institution_scope IN ('CURRENT_DEPARTMENT','SAME_INSTITUTION_OTHER_DEPARTMENT') AND faculty_id IS NULL))"
CLAIMANT = "is_claiming_faculty=0 OR (person_type='FACULTY' AND institution_scope IN ('CURRENT_DEPARTMENT','SAME_INSTITUTION_OTHER_DEPARTMENT') AND faculty_id IS NOT NULL)"
LEGACY_IDENTITY = "(faculty_id IS NULL OR (person_type='FACULTY' AND institution_scope='CURRENT_DEPARTMENT' AND student_id IS NULL)) AND (student_id IS NULL OR (person_type='STUDENT' AND institution_scope='CURRENT_DEPARTMENT' AND faculty_id IS NULL))"
LEGACY_CLAIMANT = "is_claiming_faculty=0 OR (person_type='FACULTY' AND institution_scope='CURRENT_DEPARTMENT' AND faculty_id IS NOT NULL)"


def _replace_constraints(table, identity_name, claimant_name, identity, claimant):
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(identity_name, type_="check")
        batch.drop_constraint(claimant_name, type_="check")
        batch.create_check_constraint(identity_name, identity)
        batch.create_check_constraint(claimant_name, claimant)


def upgrade():
    _replace_constraints("patent_inventors", "patent_local_identity", "patent_department_claimant", IDENTITY, CLAIMANT)
    _replace_constraints("book_contributors", "book_local_identity", "book_department_claimant", IDENTITY, CLAIMANT)


def downgrade():
    bind = op.get_bind()
    for table in ("patent_inventors", "book_contributors"):
        count = bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {table} "
            "WHERE institution_scope = 'SAME_INSTITUTION_OTHER_DEPARTMENT' "
            "AND (faculty_id IS NOT NULL OR student_id IS NOT NULL)"
        )).scalar_one()
        if count:
            raise RuntimeError("Cannot safely downgrade while cross-department Master contributor links exist.")
    _replace_constraints("patent_inventors", "patent_local_identity", "patent_department_claimant", LEGACY_IDENTITY, LEGACY_CLAIMANT)
    _replace_constraints("book_contributors", "book_local_identity", "book_department_claimant", LEGACY_IDENTITY, LEGACY_CLAIMANT)

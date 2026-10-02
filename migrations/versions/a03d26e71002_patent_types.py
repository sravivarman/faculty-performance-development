"""Constrain patent types without reclassifying existing records."""
from alembic import op
import sqlalchemy as sa

revision = 'a03d26e71002'
down_revision = 'a03d26e71001'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM patents WHERE patent_type IS NOT NULL AND patent_type NOT IN ('UTILITY','DESIGN','COPYRIGHT')")):
        raise RuntimeError('Unsupported historical patent types require manual classification; no records were converted.')
    # Legacy unspecified types remain null; new/updated API records must specify
    # an allowed type. Preserve the original unnamed lifecycle status check.
    status = sa.CheckConstraint("current_status IN ('FILED','PUBLISHED','GRANTED','REJECTED','WITHDRAWN','OTHER')", name='patent_status_valid')
    named_status = any(c['name']=='patent_status_valid' for c in sa.inspect(connection).get_check_constraints('patents'))
    with op.batch_alter_table('patents', table_args=() if named_status else (status,)) as batch:
        batch.create_check_constraint('patent_type_valid', "patent_type IS NULL OR patent_type IN ('UTILITY','DESIGN','COPYRIGHT')")


def downgrade():
    with op.batch_alter_table('patents') as batch:
        batch.drop_constraint('patent_type_valid', type_='check')

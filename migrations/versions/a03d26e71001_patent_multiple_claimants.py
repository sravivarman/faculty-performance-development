"""Allow multiple department Faculty inventor claims without rewriting records."""
from alembic import op
import sqlalchemy as sa

revision = 'a03d26e71001'
down_revision = 'f20a3dc817ab'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('uq_patent_claimant', table_name='patent_inventors')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM (SELECT patent_id FROM patent_inventors WHERE is_claiming_faculty=1 GROUP BY patent_id HAVING COUNT(*)>1)')):
        raise RuntimeError('Multiple patent claims exist; restore a backup instead of discarding attribution.')
    op.create_index('uq_patent_claimant', 'patent_inventors', ['patent_id'], unique=True, sqlite_where=sa.text('is_claiming_faculty=1'))

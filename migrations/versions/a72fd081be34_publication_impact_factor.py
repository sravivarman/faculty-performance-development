"""Preserve historical Excel impact factors as nullable publication data."""
from alembic import op
import sqlalchemy as sa

revision = 'a72fd081be34'
down_revision = 'e6d27aff4dcc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('publications', sa.Column('impact_factor', sa.Float(), nullable=True))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM publications WHERE impact_factor IS NOT NULL')):
        raise RuntimeError('Downgrade would discard stored impact factors; restore a backup instead.')
    op.drop_column('publications', 'impact_factor')

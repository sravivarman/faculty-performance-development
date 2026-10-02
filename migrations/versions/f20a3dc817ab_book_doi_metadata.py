"""Add optional book DOI metadata without rewriting historical values."""
from alembic import op
import sqlalchemy as sa

revision = 'f20a3dc817ab'
down_revision = 'c931ea46d582'
branch_labels = None
depends_on = None


def upgrade():
    for column in [sa.Column('classification', sa.String(20)), sa.Column('volume', sa.String(100)),
                   sa.Column('publication_year', sa.Integer()), sa.Column('metadata_source', sa.String(30)),
                   sa.Column('metadata_fetched_at', sa.DateTime(timezone=True)), sa.Column('raw_metadata_json', sa.JSON())]:
        op.add_column('book_publications', column)
    op.add_column('book_contributors', sa.Column('source_metadata', sa.JSON()))


def downgrade():
    fields = ['classification', 'volume', 'publication_year', 'metadata_source', 'metadata_fetched_at', 'raw_metadata_json']
    present = op.get_bind().scalar(sa.text('SELECT count(*) FROM book_publications WHERE ' + ' OR '.join(f'{field} IS NOT NULL' for field in fields)))
    sources = op.get_bind().scalar(sa.text('SELECT count(*) FROM book_contributors WHERE source_metadata IS NOT NULL'))
    if present or sources:
        raise RuntimeError('Downgrade would discard book provenance; restore a pre-upgrade backup instead.')
    op.drop_column('book_contributors', 'source_metadata')
    for field in reversed(fields):
        op.drop_column('book_publications', field)

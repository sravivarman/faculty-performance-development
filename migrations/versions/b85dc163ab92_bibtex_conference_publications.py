"""Add conference details and BibTeX provenance without recreating publications."""
from alembic import op
import sqlalchemy as sa

revision = 'b85dc163ab92'
down_revision = 'a72fd081be34'
branch_labels = None
depends_on = None


def upgrade():
    for name in ['conference_name', 'proceedings_title', 'conference_location', 'conference_organizer', 'raw_bibtex']:
        op.add_column('publications', sa.Column(name, sa.Text(), nullable=True))
    for name in ['conference_start_date', 'conference_end_date']:
        op.add_column('publications', sa.Column(name, sa.Date(), nullable=True))
    op.add_column('publications', sa.Column('source_type', sa.String(30), nullable=False, server_default='MANUAL'))
    op.execute("UPDATE publications SET source_type='DOI' WHERE metadata_source='CROSSREF'")
    op.execute("UPDATE publications SET source_type='HISTORICAL_EXCEL' WHERE remarks LIKE 'Historical journal import:%'")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM publications WHERE raw_bibtex IS NOT NULL OR conference_name IS NOT NULL OR proceedings_title IS NOT NULL OR conference_start_date IS NOT NULL OR conference_end_date IS NOT NULL OR conference_location IS NOT NULL OR conference_organizer IS NOT NULL")):
        raise RuntimeError('Downgrade would discard conference/BibTeX data; restore a backup instead.')
    for name in ['source_type', 'raw_bibtex', 'conference_organizer', 'conference_location', 'conference_end_date',
                 'conference_start_date', 'proceedings_title', 'conference_name']:
        op.drop_column('publications', name)

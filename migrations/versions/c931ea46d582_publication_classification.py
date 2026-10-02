"""Add institutional classification without changing historical indexing."""
from alembic import op
import sqlalchemy as sa

revision = "c931ea46d582"
down_revision = "b85dc163ab92"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("publications", sa.Column("classification", sa.String(20),
        sa.CheckConstraint("classification IN ('INTERNATIONAL','NATIONAL','OTHER','UNKNOWN')", name="publication_classification_valid"),
        nullable=False, server_default="UNKNOWN"))


def downgrade():
    op.drop_column("publications", "classification")

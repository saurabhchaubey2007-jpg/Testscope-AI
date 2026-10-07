"""Per-user LLM preference and structured test results."""
from alembic import op
import sqlalchemy as sa

revision = "b3c42d8f01a2"
down_revision = "9af891db5b76"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("llm_provider", sa.String(), nullable=True))
    with op.batch_alter_table("test_results") as batch:
        batch.add_column(sa.Column("cases", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("test_results") as batch:
        batch.drop_column("cases")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("llm_provider")

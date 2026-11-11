"""Add dataset ownership columns. Safe to run after 001_initial."""

from alembic import op
import sqlalchemy as sa

revision = "002_dataset_access"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("datasets")}
    if "owner_token" not in columns:
        op.add_column("datasets", sa.Column("owner_token", sa.String(length=64), nullable=True))
    if "visibility" not in columns:
        op.add_column("datasets", sa.Column("visibility", sa.String(length=16), nullable=False, server_default="public"))
    op.create_index("ix_datasets_owner_token", "datasets", ["owner_token"], unique=False, if_not_exists=True)
    op.create_index("ix_datasets_visibility", "datasets", ["visibility"], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_datasets_visibility", table_name="datasets")
    op.drop_index("ix_datasets_owner_token", table_name="datasets")
    op.drop_column("datasets", "visibility")
    op.drop_column("datasets", "owner_token")

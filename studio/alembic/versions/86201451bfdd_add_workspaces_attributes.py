"""add-workspaces-attributes

Revision ID: 86201451bfdd
Revises: 0b3a8e2ca9c1
Create Date: 2025-08-12 10:17:41.416774

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "86201451bfdd"
down_revision = "0b3a8e2ca9c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns_to_add = [
        sa.Column(
            "type",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    ]

    # Execute add_column to experiment_records in bulk
    for column in columns_to_add:
        op.add_column("workspaces", column)


def downgrade() -> None:
    columns_to_drop = [
        "type",
    ]

    # Execute drop_column to experiment_records in bulk
    for column in columns_to_drop:
        op.drop_column("workspaces", column)

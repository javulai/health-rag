"""Optional Google identity; preserve existing local accounts."""

import sqlalchemy as sa
from alembic import op

revision = "0003_google"
down_revision = "0002_chat"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(320), nullable=True))
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])


def downgrade():
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "email")
    op.drop_column("users", "google_sub")

"""track processed payment events

Revision ID: 49f0cdcfcfc5
Revises: 9f1af8713f8b
Create Date: 2026-10-07 15:23:21.470206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '49f0cdcfcfc5'
down_revision: Union[str, Sequence[str], None] = '9f1af8713f8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_payment_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
        schema="invoice",
    )


def downgrade() -> None:
    op.drop_table("processed_payment_events", schema="invoice")
"""add user and merchant usernames

Revision ID: 6bd2e15a4f01
Revises: 258046c7a5ea
Create Date: 2026-11-17 10:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6bd2e15a4f01"
down_revision: Union[str, Sequence[str], None] = "258046c7a5ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
    op.add_column("merchants", sa.Column("username", sa.String(length=50), nullable=True))

    op.execute(
        """
        UPDATE users
        SET username =
            left(
                coalesce(
                    nullif(regexp_replace(lower(split_part(email, '@', 1)), '[^a-z0-9_]', '', 'g'), ''),
                    'user'
                ),
                38
            ) || '_' || substr(replace(id::text, '-', ''), 1, 8)
        """
    )
    op.execute(
        """
        UPDATE merchants
        SET username =
            left(
                coalesce(nullif(trim(both '-' from regexp_replace(lower(name), '[^a-z0-9]+', '-', 'g')), ''), 'merchant'),
                37
            ) || '-' || substr(replace(id::text, '-', ''), 1, 8)
        """
    )

    op.alter_column("users", "username", nullable=False)
    op.alter_column("merchants", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_merchants_username", "merchants", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_merchants_username", table_name="merchants")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("merchants", "username")
    op.drop_column("users", "username")

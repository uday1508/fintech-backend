"""common foundation

Revision ID: 1c54a95f7d0b
Revises: 89b5868b3400
Create Date: 2026-11-17 10:01:18.589569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c54a95f7d0b'
down_revision: Union[str, Sequence[str], None] = '89b5868b3400'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

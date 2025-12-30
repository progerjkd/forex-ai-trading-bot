"""Fix market_data primary key for hypertable

Revision ID: 0bc7e5559506
Revises: 4bc3d057e722
Create Date: 2025-12-29 04:50:35.784561

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bc7e5559506'
down_revision: Union[str, Sequence[str], None] = '33fe8dda15a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix market_data primary key to include timestamp for hypertable compatibility."""
    # Drop the existing primary key constraint
    op.execute("ALTER TABLE trading.market_data DROP CONSTRAINT IF EXISTS market_data_pkey;")

    # Create composite primary key with id and timestamp
    op.execute("ALTER TABLE trading.market_data ADD PRIMARY KEY (id, timestamp);")


def downgrade() -> None:
    """Revert to single column primary key."""
    # Drop composite primary key
    op.execute("ALTER TABLE trading.market_data DROP CONSTRAINT IF EXISTS market_data_pkey;")

    # Recreate single column primary key
    op.execute("ALTER TABLE trading.market_data ADD PRIMARY KEY (id);")


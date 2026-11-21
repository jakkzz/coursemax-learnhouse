"""Private server-verified Google evidence and self-confirmed NRRU directory record.

Revision ID: f14b820c7d11
Revises: e92d7f04ab16
No historical evidence/identity backfill or role grants.
"""
from alembic import op
import sqlalchemy as sa
revision = 'f14b820c7d11'
down_revision = 'e92d7f04ab16'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('schoolgoogleevidence',
        sa.Column('identity_id',sa.Integer(),sa.ForeignKey('provideridentity.id'),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('user.id'),nullable=False),
        sa.Column('email',sa.String(320),nullable=False),
        sa.Column('hosted_domain',sa.String(255),nullable=True),
        sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_schoolgoogleevidence_user_id','schoolgoogleevidence',['user_id'])
    op.create_table('nrruteacheridentity',
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('user.id'),primary_key=True),
        sa.Column('identity_id',sa.Integer(),sa.ForeignKey('provideridentity.id'),nullable=False),
        sa.Column('officer_id',sa.String(20),nullable=False),
        sa.Column('officer_code',sa.String(20),nullable=False),
        sa.Column('name_th',sa.String(200),nullable=False),
        sa.Column('name_en',sa.String(200),nullable=False),
        sa.Column('confirmed_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('officer_id',name='uq_nrru_teacher_officer'))

def downgrade():
    raise RuntimeError('Directory association history must be retained; disable access instead')

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]

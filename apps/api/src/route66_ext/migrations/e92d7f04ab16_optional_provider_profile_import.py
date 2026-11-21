"""Private one-time provider profile enrichment state, no account backfill.

Revision ID: e92d7f04ab16
Revises: d84e13a6b902
"""
from alembic import op
import sqlalchemy as sa
revision = 'e92d7f04ab16'
down_revision = 'd84e13a6b902'
branch_labels = None
depends_on = None

def upgrade():
    if sa.inspect(op.get_bind()).has_table('providerprofileimport'):
        # Native create_all deployments may have installed the same table.
        inspector=sa.inspect(op.get_bind())
        columns={c['name']:c for c in inspector.get_columns('providerprofileimport')}
        expected={'user_id','identity_id','status','attempts','picture_url','display_name','locale_hint','lease_until'}
        valid=set(columns)==expected and inspector.get_pk_constraint('providerprofileimport')['constrained_columns']==['user_id']
        if valid:
            for name in ('user_id','identity_id','attempts'):
                valid=valid and isinstance(columns[name]['type'],sa.Integer)
            for name,length in {'status':16,'picture_url':2048,'display_name':160,'locale_hint':2}.items():
                valid=valid and isinstance(columns[name]['type'],sa.String) and columns[name]['type'].length==length
            valid=valid and isinstance(columns['lease_until']['type'],sa.DateTime) and columns['lease_until']['type'].timezone
            valid=valid and all(not columns[n]['nullable'] for n in ('user_id','status','attempts'))
            fks={(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns'])) for f in inspector.get_foreign_keys('providerprofileimport')}
            valid=valid and fks=={(('user_id',),'user',('id',)),(('identity_id',),'provideridentity',('id',))}
            checks={c['name'] for c in inspector.get_check_constraints('providerprofileimport')}
            valid=valid and {'ck_profile_import_status','ck_profile_import_attempts'}.issubset(checks)
        if not valid:
            raise RuntimeError('Provider profile import schema needs review')
        return
    op.create_table('providerprofileimport',
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('user.id'),primary_key=True),
        sa.Column('identity_id',sa.Integer(),sa.ForeignKey('provideridentity.id'),nullable=True),
        sa.Column('status',sa.String(16),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('picture_url',sa.String(2048),nullable=True),
        sa.Column('display_name',sa.String(160),nullable=True),
        sa.Column('locale_hint',sa.String(2),nullable=True),
        sa.Column('lease_until',sa.DateTime(timezone=True),nullable=True),
        sa.CheckConstraint("status IN ('pending','busy','complete','failed','skipped','cancelled')",name='ck_profile_import_status'),
        sa.CheckConstraint('attempts >= 0 AND attempts <= 3',name='ck_profile_import_attempts'))

def downgrade():
    raise RuntimeError('Profile import provenance must be retained; disable the feature instead')

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]

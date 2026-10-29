"""comptes clients : utilisateurs.client_id (compte de l'espace client)

Revision ID: 63ecd718cff9
Revises: 5c15b042be19
Create Date: 2026-10-29 03:47:48.752746

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '63ecd718cff9'
down_revision = '5c15b042be19'
branch_labels = None
depends_on = None


def upgrade():
    # Sans client_id : compte du gérant ; avec : compte d'un client
    with op.batch_alter_table('utilisateurs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client_id', sa.Integer(),
                                      nullable=True))
        batch_op.create_unique_constraint('uq_utilisateurs_client_id',
                                          ['client_id'])
        batch_op.create_foreign_key('fk_utilisateurs_client_id', 'clients',
                                    ['client_id'], ['id'],
                                    ondelete='CASCADE')


def downgrade():
    with op.batch_alter_table('utilisateurs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_utilisateurs_client_id',
                                 type_='foreignkey')
        batch_op.drop_constraint('uq_utilisateurs_client_id', type_='unique')
        batch_op.drop_column('client_id')

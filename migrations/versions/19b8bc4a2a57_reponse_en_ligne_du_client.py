"""reponse en ligne du client : devis.reponse_en_ligne_le

Revision ID: 19b8bc4a2a57
Revises: 63ecd718cff9
Create Date: 2026-10-29 04:06:33.758936

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '19b8bc4a2a57'
down_revision = '63ecd718cff9'
branch_labels = None
depends_on = None


def upgrade():
    # Date à laquelle le client a accepté ou refusé le devis depuis son
    # espace (vide pour les réponses saisies par le gérant)
    with op.batch_alter_table('devis', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reponse_en_ligne_le', sa.DateTime(),
                                      nullable=True))


def downgrade():
    with op.batch_alter_table('devis', schema=None) as batch_op:
        batch_op.drop_column('reponse_en_ligne_le')

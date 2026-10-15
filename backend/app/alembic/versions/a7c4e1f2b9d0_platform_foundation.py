"""Platform foundation: user roles, audit log, business settings, idempotency keys

Revision ID: a7c4e1f2b9d0
Revises: 3b7f2c9d4e10
Create Date: 2026-10-15 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a7c4e1f2b9d0'
down_revision = '3b7f2c9d4e10'
branch_labels = None
depends_on = None

ROLES = "'owner', 'manager', 'cashier', 'inventory_staff', 'accountant'"


def upgrade():
    # user.role
    op.add_column(
        'user',
        sa.Column('role', sa.String(length=32), server_default='cashier', nullable=False),
    )
    op.execute("UPDATE \"user\" SET role = 'owner' WHERE is_superuser")
    op.create_check_constraint('ck_user_role', 'user', f"role IN ({ROLES})")
    op.create_check_constraint(
        'ck_user_superuser_is_owner', 'user', "NOT is_superuser OR role = 'owner'"
    )

    # audit_log (append-only)
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('entity_type', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('entity_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('request_id', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_log_actor_id', 'audit_log', ['actor_id'], unique=False)
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index('ix_audit_log_occurred_at', 'audit_log', ['occurred_at'], unique=False)
    op.execute(
        """
        CREATE FUNCTION audit_log_reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_reject_mutation()
        """
    )

    # business_settings (singleton, seeded)
    op.create_table(
        'business_settings',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('business_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('currency_code', sqlmodel.sql.sqltypes.AutoString(length=3), nullable=False),
        sa.Column('timezone', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('allow_negative_stock', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('id = 1', name='ck_business_settings_singleton'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute(
        """
        INSERT INTO business_settings
            (id, business_name, currency_code, timezone, allow_negative_stock, updated_at)
        VALUES (1, 'Beoni', 'VND', 'Asia/Ho_Chi_Minh', false, now())
        """
    )

    # idempotency_keys
    op.create_table(
        'idempotency_keys',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('scope', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('key', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('request_hash', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('response_status', sa.Integer(), nullable=False),
        sa.Column('response_body', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope', 'key', name='uq_idempotency_keys_scope_key'),
    )
    op.create_index('ix_idempotency_keys_created_at', 'idempotency_keys', ['created_at'], unique=False)


def downgrade():
    op.drop_index('ix_idempotency_keys_created_at', table_name='idempotency_keys')
    op.drop_table('idempotency_keys')

    op.drop_table('business_settings')

    op.execute("DROP TRIGGER audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION audit_log_reject_mutation()")
    op.drop_index('ix_audit_log_occurred_at', table_name='audit_log')
    op.drop_index('ix_audit_log_entity', table_name='audit_log')
    op.drop_index('ix_audit_log_actor_id', table_name='audit_log')
    op.drop_table('audit_log')

    op.drop_constraint('ck_user_superuser_is_owner', 'user', type_='check')
    op.drop_constraint('ck_user_role', 'user', type_='check')
    op.drop_column('user', 'role')

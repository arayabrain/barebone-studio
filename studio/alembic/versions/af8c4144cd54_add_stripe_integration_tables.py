"""add stripe integration tables

Revision ID: af8c4144cd54
Revises: 0b3a8e2ca9c1
Create Date: 2025-07-22 14:45:36.895878

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "af8c4144cd54"
down_revision = "0b3a8e2ca9c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create subscription_plans table
    op.create_table(
        "subscription_plans",
        sa.Column(
            "id",
            mysql.BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("price", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("billing_cycle", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),  # Feature data in JSON format
        sa.Column("currency", mysql.TINYINT(unsigned=True), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Index("idx_subscription_plans_name", "name"),
    )

    # Create subscription_users table
    op.create_table(
        "subscription_users",
        sa.Column("id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("plan_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("expiration", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["subscription_plans.id"], name="fk_subscription_users_plan"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_subscription_users_user"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_subscription_users_user_id", "user_id"),
        sa.Index("idx_subscription_users_plan_id", "plan_id"),
        sa.Index("idx_subscription_users_expiration", "expiration"),
        sa.Index("idx_subscription_users_user_plan", "user_id", "plan_id"),
    )

    # Create subscription_payment_accounts table
    op.create_table(
        "subscription_payment_accounts",
        sa.Column(
            "id",
            mysql.BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "provider", sa.String(length=50), nullable=False
        ),  # stripe, paypal, square
        sa.Column(
            "external_account_id", sa.String(length=255), nullable=False
        ),  # Provider's customer ID
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_subscription_payment_accounts_user"
        ),
        sa.UniqueConstraint(
            "external_account_id", name="idx_unique_external_account_id"
        ),
        sa.Index("idx_subscription_payment_accounts_user", "user_id"),
        sa.Index("idx_subscription_payment_accounts_provider", "provider"),
    )
    # Create subscription_user_payments table
    op.create_table(
        "subscription_user_payments",
        sa.Column("id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "payment_method_id", sa.String(length=255), nullable=False
        ),  # Stripe Payment Method ID (pm_...)
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_subscription_user_payments_user"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_method_id", name="idx_unique_payment_method_id"),
        sa.Index("idx_subscription_user_payments_user_id", "user_id"),
    )

    # Create subscription_purchase_history table
    op.create_table(
        "subscription_purchase_history",
        sa.Column(
            "id",
            mysql.BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "purchased_plan", mysql.BIGINT(unsigned=True), nullable=False
        ),  # 1=FREE, 2=Premium, 99=Cancel
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_subscription_purchase_history_user"
        ),
        sa.Index("idx_subscription_purchase_history_user_id", "user_id"),
        sa.Index("idx_subscription_purchase_history_plan", "purchased_plan"),
        sa.Index("idx_subscription_purchase_history_created", "created_at"),
    )

    # Create taxes table for tax rates lookup

    op.create_table(
        "taxes",
        sa.Column(
            "id",
            mysql.BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "tax_type", sa.String(length=50), nullable=False
        ),  # sales_tax, vat, gst, consumption_tax
        sa.Column(
            "tax_name", sa.String(length=100), nullable=False
        ),  # "Sales Tax", "Consumption Tax"
        sa.Column(
            "tax_rate", sa.DECIMAL(8, 6), nullable=False
        ),  # e.g., 0.0825 for 8.25%, 0.10 for 10%
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),  # Active/Inactive
        sa.Column(
            "effective_date", sa.DATE(), nullable=False
        ),  # When this rate becomes effective
        sa.Column(
            "end_date", sa.DATE(), nullable=True
        ),  # When this rate expires (NULL = indefinite)
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Index("idx_taxes_active", "is_active"),
        sa.Index("idx_taxes_effective", "effective_date"),
        sa.Index("idx_taxes_type", "tax_type"),
    )

    # Create user_storage_usage table
    op.create_table(
        "user_storage_usage",
        sa.Column(
            "id",
            mysql.BIGINT(unsigned=True),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False, unique=True),
        sa.Column(
            "current_usage_bytes",
            mysql.BIGINT(unsigned=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("quota_limit_bytes", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "last_updated",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_storage_usage_user",
            ondelete="CASCADE",
        ),
        sa.Index("idx_user_storage_usage_user_id", "user_id"),
        sa.Index("idx_user_storage_usage_updated", "last_updated"),
    )


def downgrade() -> None:
    # Drop tables in reverse order (due to foreign key constraints)
    op.drop_table("user_storage_usage")
    op.drop_table("subscription_purchase_history")
    op.drop_table("subscription_user_payments")
    op.drop_table("subscription_payment_accounts")
    op.drop_table("subscription_users")
    op.drop_table("subscription_plans")
    op.drop_table("taxes")

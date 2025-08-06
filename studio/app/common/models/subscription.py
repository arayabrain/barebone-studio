from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import BIGINT, JSON, Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.sql import func
from sqlmodel import Column, Field, SQLModel


class SubscriptionPlans(SQLModel, table=True):
    __tablename__ = "subscription_plans"
    __table_args__ = (UniqueConstraint("id", name="idx_id"),)

    id: Optional[int] = Field(
        sa_column=Column(BIGINT, primary_key=True, nullable=False, autoincrement=True),
        default=None,
    )
    name: str = Field(sa_column=Column(String(100), nullable=False))
    price: int = Field(
        sa_column=Column(BIGINT, nullable=False)
    )  # Changed from float to int (cents)
    billing_cycle: int = Field(
        sa_column=Column(BIGINT, nullable=False),
        description="Billing cycle in enum format (e.g., 1 for monthly, 2 for yearly)",
    )
    # Fixed: Use JSON column type and make it properly typed
    features: Optional[Dict[str, Any]] = Field(
        sa_column=Column(JSON, nullable=False),
        description="JSON object of features included in the plan",
    )
    status: bool = Field(
        sa_column=Column(
            Boolean, nullable=False, default=True
        ),  # Fixed: Use Boolean type
        description="True=Active, False=Inactive",
    )
    currency: int = Field(
        sa_column=Column(BIGINT, nullable=False, default=1),  # Fixed: Use BIGINT
        description="Currency code in enum format (e.g., 1 for USD, 2 for JPY)",
    )
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime, nullable=False, server_default=func.current_timestamp()
        ),
    )

    @property
    def formatted_price(self) -> str:
        return f"${self.price/100:.2f}" if self.price else "Free"


class UserSubscription(SQLModel, table=True):
    __tablename__ = "subscription_users"
    __table_args__ = (UniqueConstraint("id", name="idx_id"),)

    id: Optional[int] = Field(
        sa_column=Column(BIGINT, primary_key=True, nullable=False), default=None
    )
    plan_id: int = Field(sa_column=Column(BIGINT, nullable=False))
    user_id: int = Field(sa_column=Column(BIGINT, nullable=False))
    expiration: datetime = Field(sa_column=Column(DateTime, nullable=False))
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.current_timestamp()},
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.current_timestamp()},
    )

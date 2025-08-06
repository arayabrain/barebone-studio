import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class SubscriptionPlanResponse(BaseModel):
    id: int
    name: str
    price: int
    billing_cycle: int = Field(..., description="1=Monthly, 2=Annual")
    features: Dict[str, List[Dict[str, Any]]] = Field(
        ..., description="JSON features data"
    )
    currency: int = Field(..., description="1=USD, 2=JPY")
    status: bool = Field(..., description="True=Active, False=Inactive")
    created_at: datetime

    @validator("features", pre=True)
    def parse_features(cls, v):
        """Parse features from JSON string if needed"""
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        elif isinstance(v, dict):
            return v
        else:
            return {}

    @validator("billing_cycle", pre=True)
    def parse_billing_cycle(cls, v):
        """Ensure billing_cycle is an integer"""
        try:
            return int(v) if v is not None else 1
        except (ValueError, TypeError):
            return 1

    @validator("currency", pre=True)
    def parse_currency(cls, v):
        """Ensure currency is an integer"""
        try:
            return int(v) if v is not None else 1
        except (ValueError, TypeError):
            return 1

    @validator("status", pre=True)
    def parse_status(cls, v):
        """Ensure status is a boolean"""
        if v is None:
            return True
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        try:
            return bool(int(v)) if isinstance(v, (int, float)) else bool(v)
        except (ValueError, TypeError):
            return True

    @validator("price", pre=True)
    def parse_price(cls, v):
        """Ensure price is an integer"""
        try:
            return int(v) if v is not None else 0
        except (ValueError, TypeError):
            return 0

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class UserSubscriptionResponse(BaseModel):
    id: int
    plan_id: int
    user_id: int
    expiration: datetime
    plan_name: str
    plan_price: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserSubscriptionSummary(BaseModel):
    user_id: int
    user_name: str
    user_email: str
    current_plan: Optional[str] = None
    plan_price: Optional[int] = None
    expiration: Optional[datetime] = None
    is_active: bool = False
    has_stripe_customer: bool = False
    stripe_customer_id: Optional[str] = None

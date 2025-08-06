# subscription_routes.py
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

# Import your database models and dependencies
from studio.app.common import models as common_model
from studio.app.common.core.auth.auth_dependencies import get_current_user
from studio.app.common.core.logger import AppLogger
from studio.app.common.db.database import get_db
from studio.app.common.models.subscription import SubscriptionPlans
from studio.app.common.schemas.subscriptions import (
    SubscriptionPlanResponse,
    UserSubscriptionResponse,
)
from studio.app.common.schemas.users import User

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
logger = AppLogger.get_logger()


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
def get_subscription_plans(db: Session = Depends(get_db)):
    try:
        # Query active plans
        plans = (
            db.query(SubscriptionPlans).filter(SubscriptionPlans.status == "1").all()
        )

        if not plans:
            logger.info("No subscription plans found")
            return []

        # Debug logging
        logger.info(f"Found {len(plans)} subscription plans")

        result = []
        for plan in plans:
            try:
                # Debug each plan
                logger.debug(f"Processing plan {plan.id}: {plan.name}")
                logger.debug(
                    f"Features type: {type(plan.features)}, value: {plan.features}"
                )

                # Create response object - let Pydantic validators handle conversion
                plan_response = SubscriptionPlanResponse(
                    id=plan.id,
                    name=plan.name,
                    price=plan.price,
                    billing_cycle=plan.billing_cycle,
                    features=plan.features,
                    currency=plan.currency,
                    status=plan.status,
                    created_at=plan.created_at,
                )
                result.append(plan_response)

            except Exception as plan_error:
                logger.error(f"Error processing plan {plan.id}: {plan_error}")
                # Skip this plan and continue with others
                continue

        logger.info(f"Successfully processed {len(result)} plans")
        return result

    except Exception as e:
        logger.error(f"Error fetching subscription plans: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch subscription plans: {str(e)}"
        )


@router.get(
    "/user/{user_id}",
    response_model=Optional[UserSubscriptionResponse],
)
async def get_user_subscription(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get user's current active subscription
    """
    # Check if user can access this data (either own data or admin)
    if current_user.id != user_id and not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's subscription data",
        )

    try:
        # Get the most recent active subscription
        subscription = (
            db.query(common_model.UserSubscription, common_model.SubscriptionPlans)
            .join(
                common_model.SubscriptionPlans,
                common_model.UserSubscription.plan_id
                == common_model.SubscriptionPlans.id,
            )
            .filter(
                and_(
                    common_model.UserSubscription.user_id == user_id,
                    common_model.UserSubscription.expiration > datetime.now(),
                )
            )
            .order_by(common_model.UserSubscription.expiration.desc())
            .first()
        )

        logger.info(f"Fetched subscription for user {user_id}: {subscription}")

        if not subscription:
            # Check if user has any expired subscriptions
            expired_subscription = (
                db.query(common_model.UserSubscription, common_model.SubscriptionPlans)
                .join(
                    common_model.SubscriptionPlans,
                    common_model.UserSubscription.plan_id
                    == common_model.SubscriptionPlans.id,
                )
                .filter(common_model.UserSubscription.user_id == user_id)
                .order_by(common_model.UserSubscription.expiration.desc())
                .first()
            )

            if expired_subscription:
                sub_data, plan_data = expired_subscription
                return UserSubscriptionResponse(
                    id=sub_data.id,
                    plan_id=sub_data.plan_id,
                    user_id=sub_data.user_id,
                    expiration=sub_data.expiration,
                    plan_name=plan_data.name,
                    plan_price=plan_data.price,
                    created_at=sub_data.created_at,
                    updated_at=sub_data.updated_at,
                )

            return None

        sub_data, plan_data = subscription
        return UserSubscriptionResponse(
            id=sub_data.id,
            plan_id=sub_data.plan_id,
            user_id=sub_data.user_id,
            expiration=sub_data.expiration,
            plan_name=plan_data.name,
            plan_price=plan_data.price,
            created_at=sub_data.created_at,
            updated_at=sub_data.updated_at,
        )

    except Exception as e:
        logger.error(f"Error fetching subscription for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user subscription: {str(e)}",
        )

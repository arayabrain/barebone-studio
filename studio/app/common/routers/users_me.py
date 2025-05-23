from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import auth as firebase_auth
from nbstripout import status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from studio.app.common.core.auth.auth_dependencies import get_current_user
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.users import crud_users
from studio.app.common.core.workspace.workspace_services import WorkspaceService
from studio.app.common.db.database import get_db
from studio.app.common.models.workspace import Workspace
from studio.app.common.schemas.users import SelfUserUpdate, User, UserPasswordUpdate

router = APIRouter(prefix="/users/me", tags=["users/me"])
logger = AppLogger.get_logger()


@router.get("", response_model=User)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("", response_model=User)
async def update_me(
    data: SelfUserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await crud_users.update_user(
        db, current_user.id, data, organization_id=current_user.organization.id
    )


@router.put("/password", response_model=bool)
async def update_password(
    data: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await crud_users.update_password(
        db, current_user.id, data, organization_id=current_user.organization.id
    )


@router.delete("", response_model=bool)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_ids = []
    user_uid = None

    try:
        workspaces = (
            db.query(Workspace)
            .filter(
                Workspace.user_id == current_user.id,
                Workspace.deleted.is_(False),
            )
            .all()
        )
        workspace_ids = [ws.id for ws in workspaces]

        for workspace_id in workspace_ids:
            WorkspaceService.process_workspace_deletion(
                db=db,
                workspace_id=workspace_id,
                user_id=current_user.id,
            )

        try:
            user_uid = await crud_users.delete_user(
                db=db,
                user_id=current_user.id,
                organization_id=current_user.organization.id,
            )
            db.commit()
            firebase_auth.delete_user(user_uid)
        except Exception as e:
            db.rollback()
            logger.error(
                "Failed to delete user %s: %s", current_user.id, e, exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete your user account.",
            )

    except SQLAlchemyError as db_err:
        db.rollback()
        logger.error(
            "SQLAlchemy error during user self-deletion: %s", db_err, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during account deletion.",
        )

    except Exception as e:
        db.rollback()
        logger.error("Unexpected error during user self-deletion: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting your account.",
        )

    return True

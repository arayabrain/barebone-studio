from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import LimitOffsetPage
from firebase_admin import auth as firebase_auth
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from studio.app.common.core.auth.auth_dependencies import get_admin_user
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.users import crud_users
from studio.app.common.core.workspace.workspace_services import WorkspaceService
from studio.app.common.db.database import get_db
from studio.app.common.models.workspace import Workspace
from studio.app.common.schemas.base import SortOptions
from studio.app.common.schemas.users import (
    User,
    UserCreate,
    UserSearchOptions,
    UserUpdate,
)

router = APIRouter(prefix="/admin/users", tags=["users/admin"])
logger = AppLogger.get_logger()


@router.get("", response_model=LimitOffsetPage[User])
async def list_user(
    db: Session = Depends(get_db),
    options: UserSearchOptions = Depends(),
    sortOptions: SortOptions = Depends(),
    current_admin: User = Depends(get_admin_user),
):
    return await crud_users.list_user(
        db,
        organization_id=current_admin.organization.id,
        options=options,
        sortOptions=sortOptions,
    )


@router.post("", response_model=User)
async def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    return await crud_users.create_user(
        db, data, organization_id=current_admin.organization.id
    )


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    return await crud_users.get_user(
        db, user_id, organization_id=current_admin.organization.id
    )


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    return await crud_users.update_user(
        db, user_id, data, organization_id=current_admin.organization.id
    )


@router.delete("/{user_id}", response_model=bool)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    try:
        workspaces = (
            db.query(Workspace)
            .filter(
                Workspace.user_id == user_id,
                Workspace.deleted.is_(False),
            )
            .all()
        )
        workspace_ids = [ws.id for ws in workspaces]

        for workspace_id in workspace_ids:
            WorkspaceService.process_workspace_deletion(
                db=db, workspace_id=workspace_id, user_id=user_id
            )

        # Delete user and Firebase account
        try:
            user_uid = await crud_users.delete_user(
                db=db, user_id=user_id, organization_id=current_admin.organization.id
            )
            firebase_auth.delete_user(user_uid)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("Error deleting user %s: %s", user_id, e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user.",
            )

        return True

    except SQLAlchemyError as db_err:
        logger.error("Database error: %s", db_err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while deleting user.",
        )
    except Exception as e:
        logger.error("Error deleting user: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user.",
        )

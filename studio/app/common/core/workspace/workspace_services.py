import os
import shutil
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, delete, update

from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.experiment.experiment_writer import (
    ExptConfigWriter,
    ExptDataWriter,
)
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.mode import MODE
from studio.app.common.core.utils.file_reader import get_folder_size
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.db.database import session_scope
from studio.app.common.models.experiment import ExperimentRecord
from studio.app.common.models.workspace import Workspace
from studio.app.dir_path import DIRPATH

logger = AppLogger.get_logger()


class WorkspaceService:
    @classmethod
    def _update_exp_data_usage_yaml(cls, workspace_id: str, unique_id: str, data_usage):
        # Read config
        config = ExptConfigReader.read_raw(workspace_id, unique_id)
        if not config:
            logger.error(f"[{workspace_id}/{unique_id}] does not exist")
            return

        config["data_usage"] = data_usage

        # Update & Write config
        ExptConfigWriter.write_raw(workspace_id, unique_id, config)

    @classmethod
    def _update_exp_data_usage_db(
        cls, workspace_id: str, unique_id: str, data_usage: int
    ):
        with session_scope() as db:
            try:
                exp = (
                    db.query(ExperimentRecord)
                    .filter(
                        ExperimentRecord.workspace_id == workspace_id,
                        ExperimentRecord.uid == unique_id,
                    )
                    .one()
                )
                exp.data_usage = data_usage
            except NoResultFound:
                exp = ExperimentRecord(
                    workspace_id=workspace_id,
                    uid=unique_id,
                    data_usage=data_usage,
                )
                db.add(exp)

    @classmethod
    def is_data_usage_available(cls) -> bool:
        # The workspace data usage feature is available in multiuser mode
        available = MODE.IS_MULTIUSER
        return available

    @classmethod
    def update_experiment_data_usage(cls, workspace_id: str, unique_id: str):
        workflow_dir = join_filepath([DIRPATH.OUTPUT_DIR, workspace_id, unique_id])
        if not os.path.exists(workflow_dir):
            logger.error(f"'{workflow_dir}' does not exist")
            return

        data_usage = get_folder_size(workflow_dir)

        cls._update_exp_data_usage_yaml(workspace_id, unique_id, data_usage)

        if cls.is_data_usage_available():
            cls._update_exp_data_usage_db(workspace_id, unique_id, data_usage)

    @classmethod
    def update_workspace_data_usage(
        cls, db: Session, workspace_id: str, auto_commit: bool = True
    ):
        workspace_dir = join_filepath([DIRPATH.INPUT_DIR, workspace_id])
        if not os.path.exists(workspace_dir):
            logger.error(f"'{workspace_dir}' does not exist")
            return

        input_data_usage = get_folder_size(workspace_dir)
        db.execute(
            update(Workspace)
            .where(Workspace.id == workspace_id)
            .values(input_data_usage=input_data_usage)
        )

        if auto_commit:
            db.commit()

    @classmethod
    def delete_workspace_experiment(
        cls, db: Session, workspace_id: str, unique_id: str, auto_commit: bool = False
    ) -> bool:
        # Delete experiment data
        deleted = ExptDataWriter(workspace_id, unique_id).delete_data()

        # Delete experiment database record
        if cls.is_data_usage_available():
            cls._delete_workspace_experiment_db(
                db, workspace_id, unique_id, auto_commit
            )

        return deleted

    @classmethod
    def _delete_workspace_experiment_db(
        cls, db: Session, workspace_id: str, unique_id: str, auto_commit: bool = False
    ):
        db.execute(
            delete(ExperimentRecord).where(
                ExperimentRecord.workspace_id == workspace_id,
                ExperimentRecord.uid == unique_id,
            )
        )

        if auto_commit:
            db.commit()

    @classmethod
    def sync_workspace_experiment(cls, db: Session, workspace_id: str):
        folder = join_filepath([DIRPATH.OUTPUT_DIR, workspace_id])
        if not os.path.exists(folder):
            logger.error(f"'{folder}' does not exist")
            return
        exp_records = []

        for exp_folder in Path(folder).iterdir():
            unique_id = exp_folder.name
            data_usage = get_folder_size(exp_folder.as_posix())

            cls._update_exp_data_usage_yaml(workspace_id, unique_id, data_usage)

            exp_records.append(
                ExperimentRecord(
                    workspace_id=workspace_id,
                    uid=unique_id,
                    data_usage=data_usage,
                )
            )

        if cls.is_data_usage_available():
            db.execute(
                delete(ExperimentRecord).where(
                    ExperimentRecord.workspace_id == workspace_id
                )
            )
            db.bulk_save_objects(exp_records)

    @classmethod
    def delete_workspace_contents(
        cls,
        db: Session,
        ws: Workspace,
    ):
        workspace_id = str(ws.id)
        logger.info(f"Deleting workspace data for workspace '{workspace_id}'")

        workspace_dir = join_filepath([DIRPATH.OUTPUT_DIR, workspace_id])
        hasDeleteDataArr = []

        # Delete experiment folders under workspace
        if os.path.exists(workspace_dir):
            for experiment_id in os.listdir(workspace_dir):
                # Skip hidden files and directories
                if experiment_id.startswith("."):
                    continue

                deleted = WorkspaceService.delete_workspace_experiment(
                    db, workspace_id, experiment_id, auto_commit=False
                )

                hasDeleteDataArr.append(deleted)
        else:
            logger.warning(f"Workspace directory '{workspace_dir}' does not exist")

        if all(hasDeleteDataArr):
            # Delete the workspace directory itself
            WorkspaceService.delete_workspace_files(workspace_id=workspace_id)

            # Delete input directory
            WorkspaceService.delete_workspace_files(
                workspace_id=workspace_id, is_input_dir=True
            )

            # Soft delete the workspace
            ws.deleted = True
        else:
            # Throw Exception if data was not deleted
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete workspace '{workspace_id}'",
            )

    @classmethod
    def delete_workspace_files(cls, workspace_id: str, is_input_dir: bool = False):
        if is_input_dir:
            directory = join_filepath([DIRPATH.INPUT_DIR, workspace_id])
        else:
            directory = join_filepath([DIRPATH.OUTPUT_DIR, workspace_id])
        try:
            if os.path.exists(directory):
                shutil.rmtree(directory)
                logger.info(f"Deleted directory: {directory}")
            else:
                logger.warning(f"'{directory}' already deleted or never existed")
        except Exception as e:
            logger.error(
                f"Failed to delete directory '{directory}': {e}",
                exc_info=True,
            )

    @classmethod
    def process_workspace_deletion(cls, db: Session, workspace_id: str, user_id: str):
        try:
            # Search for workspace
            ws: Workspace = (
                db.query(Workspace)
                .filter(
                    Workspace.id == workspace_id,
                    Workspace.user_id == user_id,
                    Workspace.deleted.is_(False),
                )
                .first()
            )

            if not ws:
                raise HTTPException(status_code=404, detail="Workspace not found")

            # Delete workspace storage files
            cls.delete_workspace_contents(db, ws)

            # Commit all DB changes before doing anything irreversible
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                "Error deleting or updating workspace %s: %s",
                workspace_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete or update workspace {workspace_id}.",
            )

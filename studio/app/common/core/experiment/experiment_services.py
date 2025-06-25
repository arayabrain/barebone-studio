from datetime import datetime
from glob import glob
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, delete

from studio.app.common.core.experiment.experiment import ExptConfig
from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.experiment.experiment_writer import ExptDataWriter
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.workflow.workflow_runner import WorkflowRunner
from studio.app.common.core.workspace.workspace_data_capacity_services import (
    WorkspaceDataCapacityService,
)
from studio.app.common.models.experiment import ExperimentRecord
from studio.app.common.schemas.experiment import CopyItem
from studio.app.const import DATE_FORMAT

logger = AppLogger.get_logger()


class ExperimentService:
    @classmethod
    def get_last_experiment(cls, workspace_id: str):
        last_expt_config: Optional[ExptConfig] = None
        config_paths = glob(ExptConfigReader.get_config_yaml_wild_path(workspace_id))

        for path in config_paths:
            config = ExptConfigReader.read_from_path(path)
            if not last_expt_config:
                last_expt_config = config
            elif datetime.strptime(config.started_at, DATE_FORMAT) > datetime.strptime(
                last_expt_config.started_at, DATE_FORMAT
            ):
                last_expt_config = config

        return last_expt_config

    @classmethod
    async def delete_experiment(
        cls,
        db: Session,
        remote_bucket_name: str,
        workspace_id: str,
        unique_id: str,
        auto_commit: bool = False,
    ) -> bool:
        # Delete experiment data
        result = await ExptDataWriter(
            remote_bucket_name, workspace_id, unique_id
        ).delete_data()

        # Delete experiment database record
        if WorkspaceDataCapacityService.is_available():
            cls._delete_experiment_db(db, workspace_id, unique_id, auto_commit)

        return result

    @classmethod
    def _delete_experiment_db(
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
    async def copy_experiment(
        cls, db: Session, remote_bucket_name: str, workspace_id: int, copyItem: CopyItem
    ):
        created_unique_ids = []
        try:
            for unique_id in copyItem.uidList:
                new_unique_id = WorkflowRunner.create_workflow_unique_id()
                success = await ExptDataWriter(
                    remote_bucket_name,
                    workspace_id,
                    unique_id,
                ).copy_data(new_unique_id)

                if not success:
                    raise Exception(f"Failed to copy data for unique_id: {unique_id}")

                if WorkspaceDataCapacityService.is_available():
                    cls._copy_experiment_db(
                        db,
                        workspace_id,
                        unique_id,
                        new_unique_id,
                        auto_commit=True,
                    )

                created_unique_ids.append(new_unique_id)
                logger.info(f"Copied experiment {unique_id} to {new_unique_id}")
            return True
        except Exception as e:
            logger.error(e, exc_info=True)
            # Clean up partially created data
            for created_unique_id in created_unique_ids:
                try:
                    await ExptDataWriter(
                        workspace_id,
                        created_unique_id,
                    ).delete_data()
                    logger.info(f"Cleaned up data for unique_id: {created_unique_id}")
                except Exception as cleanup_error:
                    logger.error(cleanup_error, exc_info=True)
                    logger.error(
                        f"Failed to clean up data for unique_id: {created_unique_id}",
                        exc_info=True,
                    )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to copy record. created files have been removed.",
            )

    @classmethod
    def _copy_experiment_db(
        cls,
        db: Session,
        workspace_id: str,
        unique_id: str,
        new_unique_id: str,
        auto_commit: bool = False,
    ):
        try:
            exp = (
                db.query(ExperimentRecord)
                .filter(
                    ExperimentRecord.workspace_id == workspace_id,
                    ExperimentRecord.uid == unique_id,
                )
                .one()
            )
            new_exp = ExperimentRecord(
                workspace_id=workspace_id,
                uid=new_unique_id,
                data_usage=exp.data_usage,
            )
            db.add(new_exp)
            if auto_commit:
                db.commit()
        except NoResultFound:
            # If it fails roll back the transaction
            logger.error(
                f"Experiment {unique_id} not found in workspace {workspace_id}"
            )

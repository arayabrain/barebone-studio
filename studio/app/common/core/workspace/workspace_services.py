from pathlib import Path

import yaml
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, delete, update

from studio.app.common.core.mode import MODE
from studio.app.common.core.utils.file_reader import get_folder_size
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.db.database import session_scope
from studio.app.common.models.experiment import ExperimentRecord
from studio.app.common.models.workspace import Workspace
from studio.app.dir_path import DIRPATH


class WorkspaceService:
    @classmethod
    def _update_exp_data_usage_yaml(cls, exp_filepath, data_usage):
        with open(exp_filepath, "r") as f:
            config = yaml.safe_load(f)
            config["data_usage"] = data_usage

        with open(exp_filepath, "w") as f:
            yaml.dump(config, f, sort_keys=False)

    @classmethod
    def _update_exp_data_usage_db(cls, workspace_id, unique_id, data_usage):
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
    def update_experiment_data_usage(cls, workspace_id, unique_id):
        workflow_dir = join_filepath([DIRPATH.OUTPUT_DIR, workspace_id, unique_id])
        exp_filepath = join_filepath([workflow_dir, DIRPATH.EXPERIMENT_YML])
        data_usage = get_folder_size(workflow_dir)

        cls._update_exp_data_usage_yaml(exp_filepath, data_usage)

        if not MODE.IS_STANDALONE:
            cls._update_exp_data_usage_db(workspace_id, unique_id, data_usage)

    @classmethod
    def update_workspace_data_usage(cls, db: Session, workspace_id):
        input_data_usage = get_folder_size(
            join_filepath([DIRPATH.INPUT_DIR, workspace_id])
        )
        db.execute(
            update(Workspace)
            .where(Workspace.id == workspace_id)
            .values(input_data_usage=input_data_usage)
        )
        db.commit()

    @classmethod
    def delete_workspace_experiment(cls, db: Session, workspace_id, unique_id):
        db.execute(
            delete(ExperimentRecord).where(
                ExperimentRecord.workspace_id == workspace_id,
                ExperimentRecord.uid == unique_id,
            )
        )
        db.commit()

    @classmethod
    def sync_workspace_experiment(cls, db: Session, workspace_id):
        folder = join_filepath([DIRPATH.OUTPUT_DIR, workspace_id])
        exp_records = []

        for exp_folder in Path(folder).iterdir():
            data_usage = get_folder_size(exp_folder.as_posix())
            cls._update_exp_data_usage_yaml(
                (exp_folder / DIRPATH.EXPERIMENT_YML).as_posix(), data_usage
            )
            exp_records.append(
                ExperimentRecord(
                    workspace_id=workspace_id,
                    uid=exp_folder.name,
                    data_usage=data_usage,
                )
            )

        db.execute(
            delete(ExperimentRecord).where(
                ExperimentRecord.workspace_id == workspace_id
            )
        )
        db.bulk_save_objects(exp_records)

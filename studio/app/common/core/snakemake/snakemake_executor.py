import os
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict

from snakemake.api import (
    SnakemakeApi,
    OutputSettings,
    ResourceSettings,
    StorageSettings,
    DeploymentSettings,
)
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.snakemake.smk import SmkParam
from studio.app.common.core.snakemake.smk_status_logger import SmkStatusLogger
from studio.app.common.core.snakemake.snakemake_reader import SmkConfigReader
from studio.app.common.core.utils.filepath_creater import get_pickle_file, join_filepath
from studio.app.common.core.workflow.workflow import Edge, Node
from studio.app.common.core.workflow.workflow_result import WorkflowResult
from studio.app.common.core.workspace.workspace_data_capacity_services import (
    WorkspaceDataCapacityService,
)
from studio.app.dir_path import DIRPATH

logger = AppLogger.get_logger()


def snakemake_execute(workspace_id: str, unique_id: str, params: SmkParam):
    with ProcessPoolExecutor(max_workers=1) as executor:
        logger.info("start snakemake running process.")

        future = executor.submit(
            _snakemake_execute_process, workspace_id, unique_id, params
        )
        future_result = future.result()

        logger.info("finish snakemake running process. result: %s", future_result)

        return future_result


def _snakemake_execute_process(
    workspace_id: str, unique_id: str, params: SmkParam
) -> bool:
    # ------------------------------------------------------------
    # Snakemake execution process
    # ------------------------------------------------------------

    smk_logger = SmkStatusLogger(workspace_id, unique_id)
    smk_workdir = join_filepath(
        [
            DIRPATH.OUTPUT_DIR,
            workspace_id,
            unique_id,
        ]
    )

    config_file_path = SmkConfigReader.get_config_yaml_path(workspace_id, unique_id)
    logger.debug(f"Snakemake config file path: {config_file_path}")
    logger.debug(f"Config file exists: {os.path.exists(config_file_path)}")
    logger.debug(f"Snakemake file path: {DIRPATH.SNAKEMAKE_FILEPATH}")
    logger.debug(f"Snakemake file exists: {os.path.exists(DIRPATH.SNAKEMAKE_FILEPATH)}")
    logger.debug(f"Working directory: {smk_workdir}")
    logger.debug(f"Working directory exists: {os.path.exists(smk_workdir)}")
    logger.debug(f"Conda prefix: {DIRPATH.SNAKEMAKE_CONDA_ENV_DIR}")
    logger.debug(f"Conda prefix exists: {os.path.exists(DIRPATH.SNAKEMAKE_CONDA_ENV_DIR) if DIRPATH.SNAKEMAKE_CONDA_ENV_DIR else 'None'}")
    logger.debug(f"SmkParam Execution parameters: {params}")

    # Use context manager for proper cleanup
    cores = getattr(params, 'cores', 1)

    # Use context manager for proper cleanup
    with SnakemakeApi(
        OutputSettings(
            verbose=True,
            show_failed_logs=True,
        ),
    ) as snakemake_api:
        workflow_api = snakemake_api.workflow(
            snakefile=Path(DIRPATH.SNAKEMAKE_FILEPATH),
            workdir=Path(smk_workdir),
            storage_settings=StorageSettings(),
            resource_settings=ResourceSettings(cores=cores),
            deployment_settings=DeploymentSettings(
                conda_frontend="conda",
                conda_prefix=DIRPATH.SNAKEMAKE_CONDA_ENV_DIR,
            ),
        )
        logger.debug("Workflow API created successfully")
        logger.debug("Creating DAG...")

        dag_api = workflow_api.dag()
        logger.debug("DAG created successfully")
        logger.info("Starting workflow execution...")

        try:
            dag_api.execute_workflow()
            result = True
            logger.info("snakemake_execute succeeded.")
        except Exception as e:
            result = False
            logger.error(f"snakemake_execute failed: {e}")

    smk_logger.clean_up()

    # ------------------------------------------------------------
    # Snakemake execution post process
    # ------------------------------------------------------------

    # Update workflow processing results
    WorkflowResult(workspace_id, unique_id).observe_overall()

    # Data usage calculation
    WorkspaceDataCapacityService.update_experiment_data_usage(workspace_id, unique_id)

    return result


def delete_dependencies(
    workspace_id: str,
    unique_id: str,
    smk_params: SmkParam,
    nodeDict: Dict[str, Node],
    edgeDict: Dict[str, Edge],
):
    queue = deque()

    for param in smk_params.forcerun:
        queue.append(param.nodeId)

    while True:
        # terminate condition
        if len(queue) == 0:
            break

        # delete pickle
        node_id = queue.pop()
        algo_name = nodeDict[node_id].data.label

        pickle_filepath = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                get_pickle_file(
                    workspace_id=workspace_id,
                    unique_id=unique_id,
                    node_id=node_id,
                    algo_name=algo_name,
                ),
            ]
        )
        # logger.debug(pickle_filepath)

        if os.path.exists(pickle_filepath):
            os.remove(pickle_filepath)

        # 全てのedgeを見て、node_idがsourceならtargetをqueueに追加する
        for edge in edgeDict.values():
            if node_id == edge.source:
                queue.append(edge.target)

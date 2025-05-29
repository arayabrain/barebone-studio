import os
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from typing import Dict

from snakemake import snakemake

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.snakemake.smk import SmkParam
from studio.app.common.core.snakemake.smk_status_logger import SmkStatusLogger
from studio.app.common.core.utils.filepath_creater import get_pickle_file, join_filepath
from studio.app.common.core.workflow.workflow import Edge, Node
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
    from studio.app.common.core.workspace.workspace_services import WorkspaceService

    smk_logger = SmkStatusLogger(workspace_id, unique_id)
    smk_workdir = join_filepath(
        [
            DIRPATH.OUTPUT_DIR,
            workspace_id,
            unique_id,
        ]
    )

    result = snakemake(
        DIRPATH.SNAKEMAKE_FILEPATH,
        forceall=params.forceall,
        cores=params.cores,
        use_conda=params.use_conda,
        conda_prefix=DIRPATH.SNAKEMAKE_CONDA_ENV_DIR,
        workdir=smk_workdir,
        configfiles=[
            join_filepath(
                [
                    smk_workdir,
                    DIRPATH.SNAKEMAKE_CONFIG_YML,
                ]
            )
        ],
        log_handler=[smk_logger.log_handler],
    )

    if result:
        logger.info("snakemake_execute succeeded.")
    else:
        logger.error("snakemake_execute failed..")

    WorkspaceService.update_experiment_data_usage(workspace_id, unique_id)

    smk_logger.clean_up()

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

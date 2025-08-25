import copy
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.workflow.workflow import (
    BatchInputNodeType,
    DataFilterParam,
    Message,
    NodeItem,
    RunItem,
)
from studio.app.common.core.workflow.workflow_filter import WorkflowNodeDataFilter
from studio.app.common.core.workflow.workflow_result import (
    WorkflowMonitor,
    WorkflowResult,
)
from studio.app.common.core.workflow.workflow_runner import WorkflowRunner
from studio.app.common.core.workspace.workspace_data_capacity_services import (
    WorkspaceDataCapacityService,
)
from studio.app.common.core.workspace.workspace_dependencies import (
    is_workspace_available,
    is_workspace_owner,
)

router = APIRouter(prefix="/run", tags=["run"])

logger = AppLogger.get_logger()


@router.post(
    "/{workspace_id}",
    response_model=str,
    dependencies=[Depends(is_workspace_owner)],
)
async def run(workspace_id: str, runItem: RunItem, background_tasks: BackgroundTasks):
    try:
        unique_id = WorkflowRunner.create_workflow_unique_id()
        WorkflowRunner(workspace_id, unique_id, runItem).run_workflow(background_tasks)

        logger.info("run snakemake")

        return unique_id

    except KeyError as e:
        logger.error(e, exc_info=True)
        # Pass through the specific error message for KeyErrors
        raise HTTPException(
            # Changed to 422 since it's a client configuration issue
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e).strip('"'),  # Remove quotes from the KeyError message
        )

    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run workflow.",
        )


@router.post(
    "/{workspace_id}/{uid}",
    response_model=str,
    dependencies=[Depends(is_workspace_owner)],
)
async def run_id(
    workspace_id: str, uid: str, runItem: RunItem, background_tasks: BackgroundTasks
):
    try:
        WorkflowRunner(workspace_id, uid, runItem).run_workflow(background_tasks)

        logger.info("run snakemake")
        logger.info("forcerun list: %s", runItem.forceRunList)

        return uid

    except Exception as e:
        # Check if this is a KeyError with a specific workflow yaml error message
        if isinstance(e, KeyError) and "Workflow yaml error" in str(e):
            logger.error(f"YAML validation error: {e}", exc_info=True)
            # Return 422 for YAML validation errors
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Workflow yaml error, see FAQ",
            )
        else:
            # Keep original error handling for other errors
            logger.error(e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to run workflow.",
            )


@router.post(
    "/result/{workspace_id}/{uid}",
    response_model=Dict[str, Message],
    dependencies=[Depends(is_workspace_available)],
)
async def run_result(
    workspace_id: str,
    uid: str,
    nodeDict: NodeItem,
    background_tasks: BackgroundTasks,
):
    try:
        res = WorkflowResult(workspace_id, uid).observe(nodeDict.pendingNodeIdList)
        if res:
            background_tasks.add_task(
                WorkspaceDataCapacityService.update_experiment_data_usage,
                workspace_id,
                uid,
            )
        return res
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to result workflow.",
        )


@router.post(
    "/cancel/{workspace_id}/{uid}",
    response_model=bool,
    dependencies=[Depends(is_workspace_owner)],
)
async def cancel_run(workspace_id: str, uid: str):
    try:
        return WorkflowMonitor(workspace_id, uid).cancel_run()
    except HTTPException as e:
        logger.error(e)
        raise e
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cencel workflow.",
        )


@router.post("/filter/{workspace_id}/{uid}/{node_id}", response_model=bool)
async def apply_filter(
    workspace_id: str,
    uid: str,
    node_id: str,
    background_tasks: BackgroundTasks,
    params: Optional[DataFilterParam] = None,
):
    try:
        WorkflowNodeDataFilter(
            workspace_id=workspace_id, unique_id=uid, node_id=node_id
        ).filter_node_data(params)

        background_tasks.add_task(
            WorkspaceDataCapacityService.update_experiment_data_usage, workspace_id, uid
        )

        return True
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to filter data.",
        )


@router.post(
    "/util/batch_run/{workspace_id}",
    response_model=str,
    dependencies=[Depends(is_workspace_owner)],
)
async def batch_run(
    workspace_id: str, runItem: RunItem, background_tasks: BackgroundTasks
):
    try:
        # ------------------------------------------------------------
        # Save Batch Run Template Workflow
        # ------------------------------------------------------------

        new_unique_id = WorkflowRunner.create_workflow_unique_id()

        WorkflowRunner(
            workspace_id, new_unique_id, runItem
        ).finish_workflow_without_run()

        # ------------------------------------------------------------
        # Process each Batch Run Workflows
        # #1) Data Construction
        # ------------------------------------------------------------

        # Search for batch input nodes
        batch_input_files = {}
        batch_input_counts = {}
        for node_id, node in runItem.nodeDict.items():
            if BatchInputNodeType.is_batch_input_node(node.type):
                data_paths = getattr(
                    getattr(node, "data", None), "path", None
                )  # get `node.data.path`
                batch_input_record = {node_id: node}
                batch_input_files[node_id] = (
                    data_paths if type(data_paths) is list else [data_paths]
                )
                batch_input_counts[node_id] = (
                    len(data_paths) if type(data_paths) is list else 1
                )

        # Validations
        assert batch_input_files, "No batch input nodes specified."
        batch_input_counts_min = min(batch_input_counts.values())
        batch_input_counts_max = max(batch_input_counts.values())
        if batch_input_counts_min != batch_input_counts_max:
            logger.error(
                "The number of input files in the batch nodes does not match. [%s]",
                batch_input_counts,
            )
            assert False, (
                "The number of input files in the batch nodes does not match."
                f" [{batch_input_counts_min} - {batch_input_counts_max}]"
            )
        batch_input_fixed_count = batch_input_counts_max
        del batch_input_counts_min, batch_input_counts_max

        # Transform batch input data paths
        #   into a structure suitable for batch processing.
        batch_input_records = []
        for idx in range(batch_input_fixed_count):
            batch_input_record = {}
            for node_id, data_paths in batch_input_files.items():
                batch_input_record[node_id] = data_paths[idx]

            batch_input_records.append(batch_input_record)

        # Build workflow execution data (RunItem type data)
        batch_runItems: List[RunItem] = []
        for idx, batch_input_record in enumerate(batch_input_records):
            # Duplicate and use the original RunItem
            new_run_item = copy.deepcopy(runItem)

            new_run_item.name = f"{new_run_item.name} ({new_unique_id} - {idx+1})"

            # Scan batch input records
            for node_id, data_path in batch_input_record.items():
                node_type = new_run_item.nodeDict[node_id].type

                # Construct RunItem parameters
                new_run_item.nodeDict[node_id].data.path = (
                    [data_path]
                    if node_type == BatchInputNodeType.BATCH_IMAGE
                    else data_path
                )
                new_run_item.nodeDict[node_id].data.label = data_path

                # Replace node type with corresponding standard node type.
                normal_node_type = BatchInputNodeType.refer_corresponding_node_type(
                    node_type
                )
                assert normal_node_type, f"Invalid batch node type: {node_type}"
                new_run_item.nodeDict[node_id].type = normal_node_type[0]
                new_run_item.nodeDict[node_id].data.fileType = normal_node_type[1]

            batch_runItems.append(new_run_item)

        # ------------------------------------------------------------
        # Process each Batch Run Workflows
        # #2) Start multiple workflows
        # ------------------------------------------------------------

        # TODO: (Tentative) Wait a short time before starting a batch run
        time.sleep(1)

        # Executes processing for the number of input data items
        # TODO: Parallel processing is required for performance.
        for run_item in batch_runItems:
            unique_id = WorkflowRunner.create_workflow_unique_id()
            WorkflowRunner(workspace_id, unique_id, run_item).run_workflow(
                background_tasks
            )

        logger.info(
            "Start processing batch workflows. [%d workflows]",
        )

        return new_unique_id

    except KeyError as e:
        logger.error(e, exc_info=True)
        # Pass through the specific error message for KeyErrors
        raise HTTPException(
            # Changed to 422 since it's a client configuration issue
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e).strip('"'),  # Remove quotes from the KeyError message
        )

    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run workflow.",
        )

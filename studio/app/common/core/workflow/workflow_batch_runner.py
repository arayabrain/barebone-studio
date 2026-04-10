import copy
import time
from typing import List

from fastapi import BackgroundTasks

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.workflow.workflow import BatchInputNodeType, RunItem
from studio.app.common.core.workflow.workflow_runner import WorkflowRunner

logger = AppLogger.get_logger()


class WorkflowBatchRunner:
    def __init__(self, workspace_id: str, unique_id: str, runItem: RunItem) -> None:
        self.workspace_id = workspace_id
        self.unique_id = unique_id
        self.runItem = runItem

    def run_batch_workflow(self, background_tasks: BackgroundTasks):
        # ------------------------------------------------------------
        # Save Batch Run Template Workflow
        # ------------------------------------------------------------
        WorkflowRunner(
            self.workspace_id, self.unique_id, self.runItem
        ).finish_workflow_without_run()

        # ------------------------------------------------------------
        # Process each Batch Run Workflows
        # #1) Data Construction
        # ------------------------------------------------------------
        batch_runItems = self.__build_batch_run_items()

        # ------------------------------------------------------------
        # Process each Batch Run Workflows
        # #2) Start multiple workflows
        # ------------------------------------------------------------
        self.__run_batch_workflows(batch_runItems, background_tasks)

    def __build_batch_run_items(self) -> List[RunItem]:
        """
        Building Data (RunItem) for Batch Workflows
        """

        base_unique_id = self.unique_id
        runItem = self.runItem

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

            new_run_item.name = f"{new_run_item.name} ({base_unique_id} - {idx+1})"

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

        return batch_runItems

    def __run_batch_workflows(
        self,
        batch_runItems: List[RunItem],
        background_tasks: BackgroundTasks,
    ):
        """
        Run each Batch Workflows
          Simply register all workflows to background_tasks for parallel execution.
          The actual parallel execution is handled by ProcessPoolExecutor
            in snakemake_executor.
        """

        workspace_id = self.workspace_id

        # Wait a short time before starting a batch run
        time.sleep(1)

        # Register all workflows to background_tasks
        # They will be executed in parallel automatically
        workflow_ids = []
        for idx, run_item in enumerate(batch_runItems):
            unique_id = WorkflowRunner.create_workflow_unique_id()
            WorkflowRunner(workspace_id, unique_id, run_item).run_workflow(
                background_tasks
            )
            workflow_ids.append(unique_id)

            logger.info(
                "Registered workflow %d/%d (uid: %s)",
                idx + 1,
                len(batch_runItems),
                unique_id,
            )

        logger.info(
            "All %d workflows have been registered for execution",
            len(batch_runItems),
        )

        return workflow_ids

from dataclasses import asdict
from typing import Dict, List

from studio.app.common.core.experiment.experiment_writer import ExptConfigWriter
from studio.app.common.core.snakemake.smk import FlowConfig, ForceRun, Rule, SmkParam
from studio.app.common.core.snakemake.snakemake_executor import (
    delete_dependencies,
    delete_procs_dependencies,
    snakemake_execute,
)
from studio.app.common.core.snakemake.snakemake_reader import SmkParamReader
from studio.app.common.core.snakemake.snakemake_rule import SmkRule
from studio.app.common.core.snakemake.snakemake_writer import SmkConfigWriter
from studio.app.common.core.storage.remote_storage_controller import (
    RemoteStorageController,
    RemoteSyncAction,
    RemoteSyncLockFileUtil,
    RemoteSyncStatusFileUtil,
)
from studio.app.common.core.workflow.workflow import (
    Node,
    NodeData,
    NodeType,
    NodeTypeUtil,
    ProcessType,
    RunItem,
)
from studio.app.common.core.workflow.workflow_params import get_typecheck_params
from studio.app.common.core.workflow.workflow_reader import WorkflowConfigReader
from studio.app.common.core.workflow.workflow_writer import WorkflowConfigWriter


class WorkflowRunner:
    def __init__(
        self,
        remote_bucket_name: str,
        workspace_id: str,
        unique_id: str,
        runItem: RunItem,
    ) -> None:
        self.remote_bucket_name = remote_bucket_name
        self.workspace_id = workspace_id
        self.unique_id = unique_id
        self.runItem = runItem
        self.nodeDict = WorkflowConfigReader.read_nodeDict(self.runItem.nodeDict)
        self.edgeDict = WorkflowConfigReader.read_edgeDict(self.runItem.edgeDict)

        WorkflowConfigWriter(
            self.workspace_id,
            self.unique_id,
            self.nodeDict,
            self.edgeDict,
        ).write()

        ExptConfigWriter(
            self.workspace_id,
            self.unique_id,
            self.runItem.name,
            nwbfile=get_typecheck_params(self.runItem.nwbParam, "nwb"),
            snakemake=get_typecheck_params(self.runItem.snakemakeParam, "snakemake"),
        ).write()

    def run_workflow(self, background_tasks):
        # Operate remote storage data.
        if RemoteStorageController.is_available():
            # Check for remote-sync-lock-file
            # - If lock file exists, an exception is raised (raise_error=True)
            RemoteSyncLockFileUtil.check_sync_lock_file(
                self.workspace_id, self.unique_id, raise_error=True
            )

        self.set_smk_config()

        snakemake_params: SmkParam = get_typecheck_params(
            self.runItem.snakemakeParam, "snakemake"
        )
        snakemake_params = SmkParamReader.read(snakemake_params)
        snakemake_params.forcerun = self.runItem.forceRunList

        # delete dependencies for nodes
        if len(snakemake_params.forcerun) > 0:
            delete_dependencies(
                workspace_id=self.workspace_id,
                unique_id=self.unique_id,
                smk_params=snakemake_params,
                nodeDict=self.nodeDict,
                edgeDict=self.edgeDict,
            )

        # delete dependencies for procs
        delete_procs_dependencies(
            workspace_id=self.workspace_id,
            unique_id=self.unique_id,
            forceRunList=[
                ForceRun(
                    nodeId=ProcessType.POST_PROCESS.id,
                    name=ProcessType.POST_PROCESS.label,
                )
            ],
        )

        # Operate remote storage data.
        if RemoteStorageController.is_available():
            # creating remote-sync-lock-file
            RemoteSyncLockFileUtil.create_sync_lock_file(
                self.workspace_id, self.unique_id
            )

            # creating remote_sync_status file.
            # - The status file is used to pass bucket info to subsequent processing.
            RemoteSyncStatusFileUtil.create_sync_status_file_for_processing(
                self.remote_bucket_name,
                self.workspace_id,
                self.unique_id,
                RemoteSyncAction.UPLOAD,
            )

        background_tasks.add_task(
            snakemake_execute, self.workspace_id, self.unique_id, snakemake_params
        )

    def set_smk_config(self):
        rules, last_output = self.rulefile()

        flow_config = FlowConfig(
            rules=rules,
            last_output=last_output,
        )

        SmkConfigWriter.write(self.workspace_id, self.unique_id, asdict(flow_config))

    def rulefile(self):
        endNodeList = self.get_endNodeList()

        nwbfile = get_typecheck_params(self.runItem.nwbParam, "nwb")

        rule_dict: Dict[str, Rule] = {}
        last_outputs = []

        # generate a rule for each node
        for node in self.nodeDict.values():
            if NodeTypeUtil.check_nodetype(node.type) == NodeType.DATA:
                data_common_rule = SmkRule(
                    workspace_id=self.workspace_id,
                    unique_id=self.unique_id,
                    node=node,
                    edgeDict=self.edgeDict,
                    nwbfile=nwbfile,
                )
                data_rule = None

                if node.type == NodeType.IMAGE:
                    data_rule = data_common_rule.image()
                elif node.type == NodeType.CSV:
                    data_rule = data_common_rule.csv()
                elif node.type == NodeType.FLUO:
                    data_rule = data_common_rule.csv()
                elif node.type == NodeType.BEHAVIOR:
                    data_rule = data_common_rule.csv(nodeType="behavior")
                elif node.type == NodeType.HDF5:
                    data_rule = data_common_rule.hdf5()
                elif node.type == NodeType.MATLAB:
                    data_rule = data_common_rule.mat()
                elif node.type == NodeType.MICROSCOPE:
                    data_rule = data_common_rule.microscope()

                rule_dict[node.id] = data_rule

            elif NodeTypeUtil.check_nodetype(node.type) == NodeType.ALGO:
                algo_rule = SmkRule(
                    workspace_id=self.workspace_id,
                    unique_id=self.unique_id,
                    node=node,
                    edgeDict=self.edgeDict,
                ).algo(nodeDict=self.nodeDict)

                rule_dict[node.id] = algo_rule

                if node.id in endNodeList:
                    last_outputs.append(algo_rule.output)
            else:
                assert False, f"NodeType doesn't exists: {node.type}"

        # generate a rule for implicit post-process
        post_process_rule = SmkRule(
            workspace_id=self.workspace_id,
            unique_id=self.unique_id,
            node=Node(
                id=ProcessType.POST_PROCESS.id,
                type=ProcessType.POST_PROCESS.type,
                data=NodeData(
                    label=ProcessType.POST_PROCESS.label,
                    param=None,
                    path=last_outputs,
                    type=None,
                ),
                position=None,
                style=None,
            ),
            edgeDict={},
        ).post_process()
        rule_dict[ProcessType.POST_PROCESS.type] = post_process_rule
        last_outputs.append(post_process_rule.output)

        return rule_dict, last_outputs

    def get_endNodeList(self) -> List[str]:
        returnCntDict = {key: 0 for key in self.nodeDict.keys()}
        for edge in self.edgeDict.values():
            returnCntDict[edge.source] += 1

        endNodeList = []
        for key, value in returnCntDict.items():
            if value == 0:
                endNodeList.append(key)
        return endNodeList

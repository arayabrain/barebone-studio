import os
import shutil
import uuid
from dataclasses import asdict
from glob import glob
from typing import Dict, List

from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.experiment.experiment_writer import ExptConfigWriter
from studio.app.common.core.rules.runner import Runner
from studio.app.common.core.snakemake.smk import FlowConfig, Rule, SmkParam
from studio.app.common.core.snakemake.snakemake_executor import (
    delete_dependencies,
    snakemake_execute,
)
from studio.app.common.core.snakemake.snakemake_reader import SmkParamReader
from studio.app.common.core.snakemake.snakemake_rule import SmkRule
from studio.app.common.core.snakemake.snakemake_writer import SmkConfigWriter
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.pickle_handler import PickleReader, PickleWriter
from studio.app.common.core.workflow.workflow import NodeType, NodeTypeUtil, RunItem
from studio.app.common.core.workflow.workflow_params import get_typecheck_params
from studio.app.common.core.workflow.workflow_reader import WorkflowConfigReader
from studio.app.common.core.workflow.workflow_writer import WorkflowConfigWriter
from studio.app.dir_path import DIRPATH
from studio.app.optinist.core.nwb.nwb_creater import overwrite_nwb
from studio.app.optinist.dataclass import FluoData, RoiData


class WorkflowRunner:
    def __init__(self, workspace_id: str, unique_id: str, runItem: RunItem) -> None:
        self.workspace_id = workspace_id
        self.unique_id = unique_id
        self.runItem = runItem
        self.nodeDict = self.runItem.nodeDict
        self.edgeDict = self.runItem.edgeDict

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

    @staticmethod
    def create_workflow_unique_id() -> str:
        new_unique_id = str(uuid.uuid4())[:8]
        return new_unique_id

    def run_workflow(self, background_tasks):
        self.set_smk_config()

        snakemake_params: SmkParam = get_typecheck_params(
            self.runItem.snakemakeParam, "snakemake"
        )
        snakemake_params = SmkParamReader.read(snakemake_params)
        snakemake_params.forcerun = self.runItem.forceRunList
        if len(snakemake_params.forcerun) > 0:
            delete_dependencies(
                workspace_id=self.workspace_id,
                unique_id=self.unique_id,
                smk_params=snakemake_params,
                nodeDict=self.nodeDict,
                edgeDict=self.edgeDict,
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

        SmkConfigWriter.write_raw(
            self.workspace_id, self.unique_id, asdict(flow_config)
        )

    def rulefile(self):
        endNodeList = self.get_endNodeList()

        nwbfile = get_typecheck_params(self.runItem.nwbParam, "nwb")

        rule_dict: Dict[str, Rule] = {}
        last_outputs = []

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

    @classmethod
    def _check_data_filter(cls, workspace_id, uid, node_id):
        expt_filepath = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                workspace_id,
                uid,
                DIRPATH.EXPERIMENT_YML,
            ]
        )
        exp_config = ExptConfigReader.read(expt_filepath)

        # assert exp_config.success == "success"
        assert exp_config.function[node_id].success == "success"

    @classmethod
    def filter_node_data(cls, workspace_id, uid, node_id, params):
        cls._check_data_filter(workspace_id, uid, node_id)

        workflow_config = cls.get_workflow_config(workspace_id, uid, node_id)
        node = workflow_config.nodeDict[node_id]

        pkl_filepath = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                workspace_id,
                uid,
                node_id,
                node.data.label.split(".")[0] + ".pkl",
            ]
        )

        node_dirpath = os.path.dirname(pkl_filepath)
        assert os.path.exists(pkl_filepath)

        original_pkl_filepath = pkl_filepath + ".bak"

        if params and not params.is_empty:
            if not os.path.exists(original_pkl_filepath):
                shutil.copyfile(pkl_filepath, original_pkl_filepath)
                shutil.copytree(
                    node_dirpath + "/tiff",
                    node_dirpath + "/tiff.bak",
                    dirs_exist_ok=True,
                )

            original_output_info = PickleReader.read(original_pkl_filepath)
            original_output_info = Runner.filter_data(
                original_output_info,
                params,
                type=node.data.label,
                output_dir=node_dirpath,
            )
            PickleWriter.write(pkl_filepath, original_output_info)
        else:
            # reset filter
            if not os.path.exists(original_pkl_filepath):
                return
            os.remove(pkl_filepath)
            shutil.move(original_pkl_filepath, pkl_filepath)
            shutil.rmtree(node_dirpath + "/tiff")
            os.rename(node_dirpath + "/tiff.bak", node_dirpath + "/tiff")
            original_output_info = PickleReader.read(pkl_filepath)

        cls._save_json(original_output_info, node_dirpath)

        # write config
        node.data.dataFilterParam = params
        node.data.isUpdateFilter = True
        WorkflowConfigWriter(
            workspace_id,
            uid,
            workflow_config.nodeDict,
            workflow_config.edgeDict,
        ).write()

        return

    @classmethod
    def get_workflow_config(cls, workspace_id, uid, node_id):
        workflow_filepath = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                workspace_id,
                uid,
                DIRPATH.WORKFLOW_YML,
            ]
        )
        return WorkflowConfigReader.read(workflow_filepath)

    @classmethod
    def _save_json(cls, output_info, node_dirpath):
        for k, v in output_info.items():
            if isinstance(v, (FluoData, RoiData)):
                v.save_json(node_dirpath)

            if k == "nwbfile":
                nwb_files = glob(join_filepath([node_dirpath, "[!tmp_]*.nwb"]))

                if len(nwb_files) > 0:
                    overwrite_nwb(v, node_dirpath, os.path.basename(nwb_files[0]))

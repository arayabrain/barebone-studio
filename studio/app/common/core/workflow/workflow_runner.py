import os
import shutil
import uuid
from dataclasses import asdict
from datetime import datetime
from glob import glob
from typing import Dict, List, Optional

import numpy as np

from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.experiment.experiment_writer import ExptConfigWriter
from studio.app.common.core.logger import AppLogger
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
from studio.app.common.core.workflow.workflow import (
    DataFilterParam,
    NodeType,
    NodeTypeUtil,
    RunItem,
    WorkflowRunStatus,
)
from studio.app.common.core.workflow.workflow_params import get_typecheck_params
from studio.app.common.core.workflow.workflow_reader import WorkflowConfigReader
from studio.app.common.core.workflow.workflow_writer import WorkflowConfigWriter
from studio.app.const import ORIGINAL_DATA_EXT
from studio.app.dir_path import DIRPATH
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.core.nwb.nwb_creater import overwrite_nwb
from studio.app.optinist.dataclass import FluoData, IscellData, RoiData


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

        Runner.clear_pid_file(self.workspace_id, self.unique_id)

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

    def rulefile(self) -> Dict[str, Rule]:
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


class WorkflowNodeDataFilter:
    def __init__(self, workspace_id: str, unique_id: str, node_id: str) -> None:
        self.workspace_id = workspace_id
        self.unique_id = unique_id
        self.node_id = node_id

        self.workflow_dirpath = join_filepath(
            [DIRPATH.OUTPUT_DIR, workspace_id, unique_id]
        )
        self.workflow_config = WorkflowConfigReader.read(
            join_filepath([self.workflow_dirpath, DIRPATH.WORKFLOW_YML])
        )
        self.node_dirpath = join_filepath([self.workflow_dirpath, node_id])

        # current output data path
        self.pkl_filepath = join_filepath(
            [
                self.node_dirpath,
                self.workflow_config.nodeDict[self.node_id].data.label.split(".")[0]
                + ".pkl",
            ]
        )
        self.cell_roi_filepath = join_filepath([self.node_dirpath, "cell_roi.json"])
        self.tiff_dirpath = join_filepath([self.node_dirpath, "tiff"])
        self.fluorescence_dirpath = join_filepath([self.node_dirpath, "fluorescence"])

        # original output data path
        self.original_pkl_filepath = self.pkl_filepath + ORIGINAL_DATA_EXT
        self.original_cell_roi_filepath = self.cell_roi_filepath + ORIGINAL_DATA_EXT
        self.original_tiff_dirpath = self.tiff_dirpath + ORIGINAL_DATA_EXT
        self.original_fluorescence_dirpath = (
            self.fluorescence_dirpath + ORIGINAL_DATA_EXT
        )

    def _check_data_filter(self):
        expt_filepath = join_filepath(
            [
                self.workflow_dirpath,
                DIRPATH.EXPERIMENT_YML,
            ]
        )
        exp_config = ExptConfigReader.read(expt_filepath)

        assert (
            exp_config.function[self.node_id].success == WorkflowRunStatus.SUCCESS.value
        )
        assert os.path.exists(self.pkl_filepath)

    def filter_node_data(self, params: Optional[DataFilterParam]):
        self._check_data_filter()

        if params and not params.is_empty:
            if not os.path.exists(self.original_pkl_filepath):
                self._backup_original_data()

            original_output_info = PickleReader.read(self.original_pkl_filepath)
            original_output_info = self.filter_data(
                original_output_info,
                params,
                type=self.workflow_config.nodeDict[self.node_id].data.label,
                output_dir=self.node_dirpath,
            )
            PickleWriter.write(self.pkl_filepath, original_output_info)
            self._save_json(original_output_info, self.node_dirpath)
        else:
            # reset filter
            if not os.path.exists(self.original_pkl_filepath):
                return
            self._recover_original_data()

        self._write_config(params)

    def _write_config(self, params):
        node_data = self.workflow_config.nodeDict[self.node_id].data
        node_data.draftDataFilterParam = params

        WorkflowConfigWriter(
            self.workspace_id,
            self.unique_id,
            self.workflow_config.nodeDict,
            self.workflow_config.edgeDict,
        ).write()

    def _backup_original_data(self):
        shutil.copyfile(self.pkl_filepath, self.original_pkl_filepath)

        shutil.copyfile(self.cell_roi_filepath, self.original_cell_roi_filepath)
        shutil.copytree(
            self.tiff_dirpath,
            self.original_tiff_dirpath,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            self.fluorescence_dirpath,
            self.original_fluorescence_dirpath,
            dirs_exist_ok=True,
        )
        whole_nwb_path = join_filepath([self.workflow_dirpath, "whole.nwb"])
        if os.path.exists(whole_nwb_path):
            original_nwb_filepath = join_filepath(
                [self.workflow_dirpath, "original_data.nwb"]
            )
            shutil.copyfile(whole_nwb_path, original_nwb_filepath)

    def _recover_original_data(self):
        logger = AppLogger.get_logger()
        logger.debug("Restore original data")
        os.remove(self.pkl_filepath)
        shutil.move(self.original_pkl_filepath, self.pkl_filepath)

        # trigger snakemake re-run next node by update modification time
        os.utime(
            self.pkl_filepath,
            (os.path.getctime(self.pkl_filepath), datetime.now().timestamp()),
        )

        os.remove(self.cell_roi_filepath)
        shutil.move(self.original_cell_roi_filepath, self.cell_roi_filepath)

        shutil.rmtree(self.tiff_dirpath)
        os.rename(self.original_tiff_dirpath, self.tiff_dirpath)

        shutil.rmtree(self.fluorescence_dirpath)
        os.rename(self.original_fluorescence_dirpath, self.fluorescence_dirpath)

        original_nwb_filepath = join_filepath(
            [self.workflow_dirpath, "original_data.nwb"]
        )
        if os.path.exists(original_nwb_filepath):
            os.remove(original_nwb_filepath)
            logger.debug(f"Removed backup workflow NWB: {original_nwb_filepath}")

    def _save_json(self, output_info, node_dirpath):
        for k, v in output_info.items():
            if isinstance(v, (FluoData, RoiData)):
                v.save_json(node_dirpath)

            if k == "nwbfile":
                nwb_files = glob(join_filepath([node_dirpath, "[!tmp_]*.nwb"]))

                if len(nwb_files) > 0:
                    overwrite_nwb(v, node_dirpath, os.path.basename(nwb_files[0]))

    @classmethod
    def filter_data(
        cls,
        output_info: dict,
        data_filter_param: DataFilterParam,
        type: str,
        output_dir,
    ) -> dict:
        im = output_info["edit_roi_data"].im
        fluorescence = output_info["fluorescence"].data
        dff = output_info["dff"].data if output_info.get("dff") else None
        iscell = output_info["iscell"].data

        if data_filter_param.dim1:
            dim1_filter_mask = data_filter_param.dim1_mask(
                max_size=fluorescence.shape[1]
            )
            fluorescence = fluorescence[:, dim1_filter_mask]
            if dff is not None:
                dff = dff[:, dim1_filter_mask]

        if data_filter_param.roi:
            roi_filter_mask = data_filter_param.roi_mask(max_size=iscell.shape[0])
            iscell[~roi_filter_mask] = False

        nwbfile = output_info["nwbfile"]
        function_id = list(nwbfile[type][NWBDATASET.POSTPROCESS].keys())[0]
        nwbfile[type][NWBDATASET.COLUMN][function_id]["data"] = iscell
        nwbfile[type][NWBDATASET.FLUORESCENCE][function_id]["Fluorescence"][
            "data"
        ] = fluorescence.T

        info = {
            **output_info,
            "cell_roi": RoiData(
                np.nanmax(im[iscell != 0], axis=0, initial=np.nan),
                output_dir=output_dir,
                file_name="cell_roi",
            ),
            "fluorescence": FluoData(fluorescence, file_name="fluorescence"),
            "iscell": IscellData(iscell),
            "nwbfile": nwbfile,
        }

        if dff is not None:
            info["dff"] = FluoData(dff, file_name="dff")
        else:
            info["all_roi"] = RoiData(
                np.nanmax(im, axis=0, initial=np.nan),
                output_dir=output_dir,
                file_name="all_roi",
            )
            info["non_cell_roi"] = RoiData(
                np.nanmax(im[iscell == 0], axis=0, initial=np.nan),
                output_dir=output_dir,
                file_name="non_cell_roi",
            )

        return info

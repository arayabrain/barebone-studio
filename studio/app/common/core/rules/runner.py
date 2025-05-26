import copy
import gc
import json
import os
import time
import traceback
from dataclasses import asdict
from pathlib import Path

from filelock import FileLock

from studio.app.common.core.experiment.experiment import ExptOutputPathIds
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.snakemake.smk import Rule
from studio.app.common.core.snakemake.snakemake_rule import SmkRule
from studio.app.common.core.utils.config_handler import ConfigReader
from studio.app.common.core.utils.file_reader import JsonReader
from studio.app.common.core.utils.filelock_handler import FileLockUtils
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.filepath_finder import find_condaenv_filepath
from studio.app.common.core.utils.pickle_handler import PickleReader, PickleWriter
from studio.app.common.schemas.workflow import WorkflowPIDFileData
from studio.app.dir_path import DIRPATH
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.core.nwb.nwb_creater import (
    merge_nwbfile,
    overwrite_nwbfile,
    save_nwb,
)
from studio.app.wrappers import wrapper_dict

logger = AppLogger.get_logger()


class Runner:
    RUN_PROCESS_PID_FILE = "pid.json"

    @classmethod
    def run(cls, __rule: Rule, last_output, run_script_path: str):
        try:
            logger.info("start rule runner")

            # write pid file
            workflow_dirpath = str(Path(__rule.output).parent.parent)
            cls.write_pid_file(workflow_dirpath, __rule.type, run_script_path)

            input_info = cls.read_input_info(__rule.input)
            cls.__change_dict_key_exist(input_info, __rule)
            nwbfile = input_info["nwbfile"]

            # input_info
            for key in list(input_info):
                if key not in __rule.return_arg.values():
                    logger.debug(
                        f"Runner - Removing key '{key}' (not in expected return args)"
                    )
                    input_info.pop(key)
            logger.debug(
                f"Runner - After filtering, input_info keys: {list(input_info.keys())}"
            )

            # output_info
            output_info = cls.__execute_function(
                __rule.path,
                __rule.params,
                nwbfile.get("input"),
                os.path.dirname(__rule.output),
                input_info,
            )

            # nwbfileの設定
            output_info["nwbfile"] = cls.__save_func_nwb(
                f"{__rule.output.split('.')[0]}.nwb",
                __rule.type,
                nwbfile,
                output_info,
            )

            # 各関数での結果を保存
            PickleWriter.write(__rule.output, output_info)

            # NWB全体保存
            if __rule.output in last_output:
                # 全体の結果を保存する
                path = join_filepath(os.path.dirname(os.path.dirname(__rule.output)))
                path = join_filepath([path, "whole.nwb"])
                cls.save_all_nwb(path, output_info["nwbfile"])

            logger.info("rule output: %s", __rule.output)

            del input_info, output_info
            gc.collect()

        except Exception as e:
            # logging error
            err_msg = list(traceback.TracebackException.from_exception(e).format())
            logger.error("\n".join(err_msg))

            # save error info to node pickle data.
            PickleWriter.write_error(__rule.output, e)

    @classmethod
    def __get_pid_file_path(cls, workspace_id: str, unique_id: str) -> str:
        pid_file_path = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                workspace_id,
                unique_id,
                cls.RUN_PROCESS_PID_FILE,
            ]
        )
        return pid_file_path

    @classmethod
    def write_pid_file(
        cls, workflow_dirpath: str, func_name: str, run_script_path: str
    ) -> None:
        """
        save snakemake script file path and PID of current running algo function
        """
        pid_data = WorkflowPIDFileData(
            last_pid=os.getpid(),
            func_name=func_name,
            last_script_file=run_script_path,
            create_time=time.time(),
        )

        ids = ExptOutputPathIds(workflow_dirpath)
        pid_file_path = cls.__get_pid_file_path(ids.workspace_id, ids.unique_id)

        with open(pid_file_path, "w") as f:
            json.dump(asdict(pid_data), f)

            # Force immediate write of pid file
            f.flush()
            os.fsync(f.fileno())

    @classmethod
    def clear_pid_file(cls, workspace_id: str, unique_id: str) -> None:
        pid_file_path = cls.__get_pid_file_path(workspace_id, unique_id)
        if os.path.exists(pid_file_path):
            os.remove(pid_file_path)

    @classmethod
    def read_pid_file(cls, workspace_id: str, unique_id: str) -> WorkflowPIDFileData:
        pid_file_path = cls.__get_pid_file_path(workspace_id, unique_id)
        if not os.path.exists(pid_file_path):
            return None

        pid_data_json = JsonReader.read(pid_file_path)
        pid_data = WorkflowPIDFileData(**pid_data_json)

        return pid_data

    @classmethod
    def __save_func_nwb(cls, save_path, name, nwbfile, output_info):
        if "nwbfile" in output_info:
            nwbfile[name] = output_info["nwbfile"]
            save_nwb(
                save_path,
                nwbfile["input"],
                output_info["nwbfile"],
            )
        return nwbfile

    @classmethod
    def save_all_nwb(cls, save_path, all_nwbfile):
        input_nwbfile = all_nwbfile["input"]
        all_nwbfile.pop("input")
        nwbconfig = {}
        for x in all_nwbfile.values():
            nwbconfig = merge_nwbfile(nwbconfig, x)

        # Controls locking for simultaneous writing to nwbfile from multiple nodes.
        lock_path = FileLockUtils.get_lockfile_path(save_path)
        with FileLock(lock_path, timeout=120):
            if os.path.exists(save_path):
                overwrite_nwbfile(save_path, nwbconfig)
            else:
                save_nwb(save_path, input_nwbfile, nwbconfig)

    @classmethod
    def __execute_function(cls, path, params, nwb_params, output_dir, input_info):
        wrapper = cls.__dict2leaf(wrapper_dict, path.split("/"))
        func = copy.deepcopy(wrapper["function"])
        output_info = func(
            params=params, nwbfile=nwb_params, output_dir=output_dir, **input_info
        )
        del func
        gc.collect()

        try:
            # Initialize CONFIG dictionary structure
            function_id = ExptOutputPathIds(output_dir).function_id
            if "nwbfile" not in output_info:
                output_info["nwbfile"] = {}

            if NWBDATASET.CONFIG not in output_info["nwbfile"]:
                output_info["nwbfile"][NWBDATASET.CONFIG] = {}
            if function_id not in output_info["nwbfile"][NWBDATASET.CONFIG]:
                output_info["nwbfile"][NWBDATASET.CONFIG][function_id] = {}
        except Exception as e:
            logger.warning(f"Failed to initialize CONFIG dataset for{function_id}:{e}")

        # Store conda env config in CONFIG dataset
        try:
            conda_name = wrapper.get("conda_name")
            conda_env_path = find_condaenv_filepath(conda_name)
            conda_config = ConfigReader.read(conda_env_path)
            config_str = json.dumps(conda_config, separators=(",", ":"))

            # Store conda env config in CONFIG dataset
            output_info["nwbfile"][NWBDATASET.CONFIG][function_id][
                "conda_config"
            ] = config_str
        except Exception as e:
            logger.info(f"Failed to add conda environment config to NWB file: {e}")

        try:
            # Store node parameters in CONFIG dataset
            params_str = json.dumps(params, separators=(",", ":"))
            output_info["nwbfile"][NWBDATASET.CONFIG][function_id][
                "node_params"
            ] = params_str
        except Exception as e:
            logger.warning(f"Failed to add node parameters to NWB file: {e}")

        return output_info

    @classmethod
    def __change_dict_key_exist(cls, input_info, rule_config: Rule):
        for return_arg_key, arg_name in rule_config.return_arg.items():
            return_name = return_arg_key.split(SmkRule.RETURN_ARG_KEY_DELIMITER)[0]
            if return_name in input_info:
                input_info[arg_name] = input_info.pop(return_name)

    @classmethod
    def read_input_info(cls, input_files):
        input_info = {}
        logger.debug(f"Runner - Reading {len(input_files)} input files")
        for i, filepath in enumerate(input_files):
            load_data = PickleReader.read(filepath)
            logger.debug(f"Runner - File {i+1} contains keys: {list(load_data.keys())}")

            # validate load_data content
            assert PickleReader.check_is_valid_node_pickle(
                load_data
            ), f"Invalid node input data content. [{filepath}]"

            merged_nwb = cls.__deep_merge(
                load_data.pop("nwbfile", {}), input_info.pop("nwbfile", {})
            )
            input_info = dict(list(load_data.items()) + list(input_info.items()))
            input_info["nwbfile"] = merged_nwb
            logger.debug(
                f"Runner - Final merged input_info keys: {list(input_info.keys())}"
            )
        return input_info

    @classmethod
    def __deep_merge(cls, dict1, dict2):
        if not isinstance(dict1, dict) or not isinstance(dict2, dict):
            return dict2
        merged = dict1.copy()
        for k, v in dict2.items():
            if k in merged and isinstance(merged[k], dict):
                merged[k] = cls.__deep_merge(merged[k], v)
            else:
                merged[k] = v
        return merged

    @classmethod
    def __dict2leaf(cls, root_dict: dict, path_list):
        path = path_list.pop(0)
        if len(path_list) > 0:
            return cls.__dict2leaf(root_dict[path], path_list)
        else:
            return root_dict[path]

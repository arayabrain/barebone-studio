import os
import platform
import subprocess
from typing import Dict

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.filepath_finder import find_condaenv_filepath
from studio.app.common.core.workflow.workflow import NodeType, NodeTypeUtil
from studio.app.const import FILETYPE
from studio.app.dir_path import DIRPATH
from studio.app.wrappers import wrapper_dict

logger = AppLogger.get_logger()


class SmkUtils:
    @classmethod
    def input(cls, details):
        if NodeTypeUtil.check_nodetype_from_filetype(details["type"]) == NodeType.DATA:
            if details["type"] in [FILETYPE.IMAGE]:
                return [join_filepath([DIRPATH.INPUT_DIR, x]) for x in details["input"]]
            else:
                return join_filepath([DIRPATH.INPUT_DIR, details["input"]])
        else:
            return [join_filepath([DIRPATH.OUTPUT_DIR, x]) for x in details["input"]]

    @classmethod
    def output(cls, details):
        return join_filepath([DIRPATH.OUTPUT_DIR, details["output"]])

    @classmethod
    def dict2leaf(cls, root_dict: dict, path_list):
        """Recursively unpacks nested dictionary using path list to get leaf value"""
        path = path_list.pop(0)
        if len(path_list) > 0:
            return cls.dict2leaf(root_dict[path], path_list)
        else:
            return root_dict[path]

    @classmethod
    def conda(cls, details):
        """Gets conda env path and handles special case of CaImAn on Apple Silicon"""
        if NodeTypeUtil.check_nodetype_from_filetype(details["type"]) == NodeType.DATA:
            return None

        wrapper = cls.dict2leaf(wrapper_dict, details["path"].split("/"))

        if "conda_name" in wrapper:
            conda_name = wrapper["conda_name"]
            conda_filepath = join_filepath([DIRPATH.CONDAENV_DIR, "envs", conda_name])

            # Handle CaImAn params modification if needed
            is_caiman = "caiman" in conda_name.lower()
            if is_caiman and cls.is_apple_silicon():
                # Modify the parameters directly in the details dictionary
                if "params" in details:
                    details["params"] = cls.modify_caiman_params(details["params"])

            # Original conda path resolution logic
            if os.path.exists(conda_filepath):
                return conda_filepath
            else:
                return find_condaenv_filepath(conda_name)

        return None

    @staticmethod
    def is_apple_silicon():
        """
        Detects if running on Apple Silicon CPU, including under Rosetta 2 emulation
        """
        try:
            # Check the architecture reported by Python
            python_arch = platform.machine()

            # Check the underlying hardware architecture using sysctl
            cmd = ["sysctl", "-n", "hw.machine"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            hardware_arch = result.stdout.strip()

            # If Python reports x86_64 but hardware is arm64, we're running Rosetta 2
            # CaImAn cnn is currently failing with Rosetta 2
            if python_arch == "x86_64" and hardware_arch == "arm64":
                return "arm64"  # Underlying hardware is Apple Silicon
            else:
                return hardware_arch

        except Exception as e:
            logger.info("Failed to detect Apple Silicon: %s", e)
            return False

    @classmethod
    def modify_caiman_params(cls, params: Dict) -> Dict:
        """
        Modifies CaImAn params to be compatible with Apple Silicon by disabling CNN
        """
        if params is None:
            return params

        # Create a deep copy to avoid modifying the original
        modified_params = params.copy()

        # Check if advanced parameters exist and contain quality evaluation params
        if "advanced" in modified_params:
            if "quality_evaluation_params" in modified_params["advanced"]:
                modified_params["advanced"]["quality_evaluation_params"][
                    "use_cnn"
                ] = False
                logger.info("Disabled CNN usage in CaImAn parameters for Apple Silicon")

        # Also check top-level parameters
        if "quality_evaluation_params" in modified_params:
            modified_params["quality_evaluation_params"]["use_cnn"] = False
            logger.info("Disabled CNN usage in CaImAn parameters for Apple Silicon")

        return modified_params

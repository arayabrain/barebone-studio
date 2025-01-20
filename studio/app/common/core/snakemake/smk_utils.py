import logging
import os
import platform

import yaml

from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.filepath_finder import find_condaenv_filepath
from studio.app.common.core.workflow.workflow import NodeType, NodeTypeUtil
from studio.app.const import FILETYPE
from studio.app.dir_path import DIRPATH
from studio.app.wrappers import wrapper_dict


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
        path = path_list.pop(0)
        if len(path_list) > 0:
            return cls.dict2leaf(root_dict[path], path_list)
        else:
            return root_dict[path]

    @classmethod
    def conda(cls, details):
        """Gets base conda environment path"""
        if NodeTypeUtil.check_nodetype_from_filetype(details["type"]) == NodeType.DATA:
            return None

        wrapper = cls.dict2leaf(wrapper_dict, details["path"].split("/"))

        if "conda_name" in wrapper:
            conda_name = wrapper["conda_name"]
            conda_filepath = f"{DIRPATH.CONDAENV_DIR}/envs/{conda_name}"
            print("========== CONDA CALLED ==========") 
            if os.path.exists(conda_filepath):
                base_conda = conda_filepath
            else:
                base_conda = find_condaenv_filepath(conda_name)

            # Apply platform-specific modifications if needed
            return cls.get_platform_specific_conda(base_conda)

        return None

    @staticmethod
    def is_apple_silicon():
        return platform.system() == "Darwin" and platform.machine() == "arm64"

    @classmethod
    def test_tensorflow_load(cls):
        try:
            import tensorflow as tf

            tf.config.list_physical_devices("GPU")
            return True
        except Exception as e:
            logging.warning(f"TensorFlow test load failed: {e}")
            return False

    @classmethod
    def get_platform_specific_conda(cls, base_conda):
        """Modify conda environment for platform-specific requirements"""
        print("========== PLATFORM SPECIFIC CONDA CALLED ==========")  # Very obvious debug print
        logging.getLogger().info("PLATFORM SPECIFIC CONDA CALLED")
        print(f"Platform: {platform.system()}")
        print(f"Machine: {platform.machine()}")
        print(f"Is Apple Silicon: {cls.is_apple_silicon()}")
        if base_conda is None:
            logging.getLogger().debug("No conda environment specified")
            return None

        if "caiman" not in base_conda.lower():
            logging.getLogger().debug(
                f"Not a CaImAn environment, skipping change: {base_conda}"
            )
            return base_conda

        if cls.is_apple_silicon():
            logging.getLogger().info("Detected Apple Silicon platform")
            try:
                with open(base_conda, "r") as f:
                    conda_env = yaml.safe_load(f)

                logging.getLogger().debug(
                    f"Original dependencies: {conda_env['dependencies']}"
                )

                # Add Apple channel if not present
                if "channels" not in conda_env:
                    conda_env["channels"] = []
                if "apple" not in conda_env["channels"]:
                    conda_env["channels"].insert(0, "apple")

                # Remove incompatible packages
                conda_env["dependencies"] = [
                    dep
                    for dep in conda_env["dependencies"]
                    if not isinstance(dep, str)
                    or not any(x in dep for x in ["tensorflow", "keras", "xbyak"])
                ]

                # Add Apple Silicon specific dependencies
                apple_deps = [
                    "tensorflow-deps",
                    "h5py<3.0.0",  # Version constraint to avoid HDF5 issues
                ]

                # Ensure pip is in dependencies
                if "pip" not in conda_env["dependencies"]:
                    conda_env["dependencies"].append("pip")

                # Add or update pip dependencies
                pip_deps = {
                    "tensorflow-macos>=2.13.0",
                    "tensorflow-metal>=1.0.0",
                    "keras>=2.13.0",
                }

                # Find or create pip section in dependencies
                pip_section = None
                for dep in conda_env["dependencies"]:
                    if isinstance(dep, dict) and "pip" in dep:
                        pip_section = dep
                        break

                if pip_section is None:
                    pip_section = {"pip": list(pip_deps)}
                    conda_env["dependencies"].append(pip_section)
                else:
                    # Update existing pip dependencies
                    current_pip_deps = set(pip_section["pip"])
                    pip_section["pip"] = list(current_pip_deps.union(pip_deps))

                # Add conda dependencies
                conda_env["dependencies"].extend(apple_deps)

                # Add environment variables
                if "variables" not in conda_env:
                    conda_env["variables"] = {}

                conda_env["variables"].update(
                    {
                        "CAIMAN_SKIP_CNN": "1"
                        if not cls.test_tensorflow_load()
                        else "0",
                        "TF_FORCE_GPU_ALLOW_GROWTH": "true",
                        "PYTORCH_ENABLE_MPS_FALLBACK": "1",
                    }
                )

                # Write updated environment file
                with open(base_conda, "w") as f:
                    yaml.dump(conda_env, f, default_flow_style=False, sort_keys=False)

                logging.getLogger().info("Updated environment file for Apple Silicon")
                return base_conda

            except Exception as e:
                logging.error(
                    f"Error modifying conda environment for Apple Silicon: {e}"
                )
                return base_conda

        return base_conda

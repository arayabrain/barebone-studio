import os

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
    def conda(cls, details):
        if NodeTypeUtil.check_nodetype_from_filetype(details["type"]) == NodeType.DATA:
            return None

        wrapper = cls.dict2leaf(wrapper_dict, details["path"].split("/"))

        if "conda_name" in wrapper:
            conda_name = wrapper["conda_name"]
            return cls.get_conda_env_filepath(conda_name)

        return None

    @classmethod
    def get_conda_env_filepath(cls, conda_name) -> str:
        conda_env_filepath = f"{DIRPATH.CONDAENV_DIR}/envs/{conda_name}"
        if os.path.exists(conda_env_filepath):
            return conda_env_filepath
        else:
            return find_condaenv_filepath(conda_name)

    @classmethod
    def dict2leaf(cls, root_dict: dict, path_list):
        path = path_list.pop(0)
        if len(path_list) > 0:
            return cls.dict2leaf(root_dict[path], path_list)
        else:
            return root_dict[path]


class SmkInternalUtils:
    """
    This class defines functions that directly use Snakemake's internal API.
    - Notes.
      - If there are API specification changes due to future version upgrades
        of Snakemake, it is necessary to follow the changes.
      - Initially, we have confirmed the operation with the following versions
        of snakemake.
        - snakemake v7.30
    """

    """
    NOTE: This path is defined below:
      - snakemake.persistence.Persistence.__init__
    """
    SMK_CONDA_ENV_ROOT_PATH = ".snakemake/conda"

    @classmethod
    def verify_conda_env_exists(
        cls,
        conda_name: str,
        conda_env_rootpath: str = None,
        conda_env_filepath: str = None,
    ) -> bool:
        """
        Verify that the specified conda environment has been generated by snakemake.
        """
        from snakemake import Workflow
        from snakemake.deployment.conda import Env

        """
        Get the root path to the conda env destination managed by snakemake.
        NOTE:
          This path is generated in `Persistence.__init__`, but since the above function
          also performs initialization processes other than path generation,
          Persistence is not used directly here.
        """
        if conda_env_rootpath is None:
            conda_env_rootpath = os.path.join(
                DIRPATH.ROOT_DIR, cls.SMK_CONDA_ENV_ROOT_PATH
            )

        # Get the path of the conda env configuration file
        if conda_env_filepath is None:
            conda_env_filepath = SmkUtils.get_conda_env_filepath(conda_name) or ""
        if not os.path.exists(conda_env_filepath):
            assert False, (
                "Invalid conda_env_filepath. "
                f"[conda_name: {conda_name}] [env_filepath: {conda_env_filepath}]"
            )

        """
        Get the path of the target conda env generated by snakemake.
        NOTE: This determination is defined as follows:
          - snakemake.deployment.conda.CondaEnvFileSpec.get_conda_env
        """
        conda_env = Env(
            Workflow(snakefile="Snakefile"),
            env_file=conda_env_filepath,
            env_dir=conda_env_rootpath,
            container_img=None,
            cleanup=None,
        )
        conda_env_dirpath = conda_env.address or ""

        """
        Verify that conda env has been created by snakemake
        NOTE: This determination is defined as follows:
          - snakemake.deployment.conda.Env.create
        """
        is_conda_env_exists = os.path.exists(
            os.path.join(conda_env_dirpath, "env_setup_start")
        ) and os.path.exists(os.path.join(conda_env_dirpath, "env_setup_done"))

        return is_conda_env_exists

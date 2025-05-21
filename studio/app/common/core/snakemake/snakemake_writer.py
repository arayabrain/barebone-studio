from studio.app.common.core.logger import AppLogger
from studio.app.common.core.snakemake.smk_utils import SmkUtils
from studio.app.common.core.utils.config_handler import ConfigWriter
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.dir_path import DIRPATH

AppLogger.get_logger()
logger = AppLogger.get_logger()


class SmkConfigWriter:
    @staticmethod
    def write_raw(workspace_id, unique_id, config):
        config = SmkUtils.replace_nwbfile_with_reference(config)
        ConfigWriter.write(
            dirname=join_filepath([DIRPATH.OUTPUT_DIR, workspace_id, unique_id]),
            filename=DIRPATH.SNAKEMAKE_CONFIG_YML,
            config=config,
        )

import logging
import os

from studio.app.common.core.utils.file_reader import Reader
from studio.app.common.core.utils.filepath_creater import (
    create_directory,
    join_filepath,
)
from studio.app.common.schemas.workflow import WorkflowErrorInfo
from studio.app.dir_path import DIRPATH


class SmkStatusLogger:
    """
    ATTENTION: Since the Snakemake library automatically creates thread for workflow
      and shares the same loggers in the library, all workflows running at the same time
      will use same log data.
    """

    ERROR_LOG_NAME = "error.log"

    @classmethod
    def get_logger(cls, workspace_id: str, unique_id: str) -> logging.Logger:
        log_file_path = cls.__init_error_log_file(workspace_id, unique_id)

        logger = logging.getLogger(unique_id)

        # setting FileHandler
        fh = logging.FileHandler(log_file_path)
        fh.setLevel(logging.ERROR)
        fmt = logging.Formatter(
            "%(asctime)s : %(levelname)s - %(filename)s - %(message)s"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        fh.close()

        return logger

    @classmethod
    def __get_error_log_file_path(cls, workspace_id: str, unique_id: str):
        output_dirpath = join_filepath(
            [
                DIRPATH.OUTPUT_DIR,
                workspace_id,
                unique_id,
            ]
        )
        log_file_path = f"{output_dirpath}/{cls.ERROR_LOG_NAME}"

        return log_file_path

    @classmethod
    def __init_error_log_file(cls, workspace_id: str, unique_id: str) -> str:
        log_file_path = cls.__get_error_log_file_path(workspace_id, unique_id)
        output_dirpath = os.path.dirname(log_file_path)

        create_directory(output_dirpath)

        if os.path.exists(log_file_path):
            try:
                os.remove(log_file_path)
            except Exception as e:
                print("[Exception][Logger]", e)

        return log_file_path

    @classmethod
    def get_error_content(cls, workspace_id: str, unique_id: str) -> WorkflowErrorInfo:
        log_file_path = cls.__get_error_log_file_path(workspace_id, unique_id)

        if os.path.exists(log_file_path):
            error_log = Reader.read(log_file_path)
            has_error = error_log != ""
        else:
            error_log = None
            has_error = False

        return WorkflowErrorInfo(has_error=has_error, error_log=error_log)

    def __init__(self, workspace_id, unique_id):
        self.workspace_id = workspace_id
        self.unique_id = unique_id
        self.logger: logging.Logger = __class__.get_logger(workspace_id, unique_id)

    def clean_up(self):
        """
        remove all handlers from this logger
        """
        self.logger.handlers.clear()

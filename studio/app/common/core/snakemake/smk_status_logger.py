import glob
import logging
import os
from typing import Dict

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.rules.runner import Runner
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

    def log_handler(self, msg: Dict[str, str] = None):
        """
        msg:
            level:
                "job_info": jobの始まりを通知。inputやoutputがある
                "job_finished": jobの終了を通知。
        """
        # pass
        # # has error.
        # if "exception" in msg:
        #     self.logger.error(msg)

        # Inspect log contents
        if "level" in msg and "debug" in msg["level"]:
            level = msg["level"]
            if "debug" in level and "msg" in msg:
                # Inspects for error logs
                if "Traceback" in msg["msg"]:
                    # check if the message is thrown by killing process action
                    if any(
                        err in msg["msg"]
                        for err in ["Signals.SIGTERM", "exit status 15"]
                    ):
                        pid_data = Runner.read_pid_file(
                            self.workspace_id, self.unique_id
                        )

                        # since multiple running workflow share log data,
                        # check if message really belongs to the current workflow
                        if (
                            pid_data is not None
                            and pid_data.last_script_file in msg["msg"]
                        ):
                            self.logger.error("Workflow cancelled")
                        else:
                            self.logger.error(msg)

                    # for any other errors
                    else:
                        self.logger.error(msg)

    def clean_up(self):
        """
        remove all handlers from this logger
        """
        self.logger.handlers.clear()

    def extract_errors_from_snakemake_log(self, workdir: str):
        """
        Extract error information from Snakemake's log file and write to error.log
        """

        logger = AppLogger.get_logger()

        try:
            # Find the most recent Snakemake log file
            log_pattern = os.path.join(workdir, ".snakemake", "log", "*.snakemake.log")
            log_files = glob.glob(log_pattern)

            if not log_files:
                logger.warning("No Snakemake log files found")
                return

            # Check the log file for errors/tracebacks
            latest_log = max(log_files, key=os.path.getctime)
            logger.info(f"Reading Snakemake log file: {latest_log}")
            with open(latest_log, "r") as f:
                log_content = f.read()

            # Look for traceback patterns that indicate errors
            if "Traceback" in log_content or "Exception" in log_content:
                # Extract only error-related sections
                error_sections = self._extract_error_sections(log_content)

                if error_sections:
                    msg = {"level": "debug", "msg": error_sections}

                    self.log_handler(msg)
                    logger.info("Copied error sections from Snakemake log to error.log")
                else:
                    logger.info("No relevant error sections found after filtering")
            else:
                logger.info("No errors found in Snakemake log")

        except Exception as e:
            logger.error(f"Failed to extract errors from Snakemake log: {e}")

    def _extract_error_sections(self, log_content: str) -> str:
        """Extract error sections - much simpler approach"""
        lines = log_content.split("\n")

        # Find any line containing "Traceback"
        for i, line in enumerate(lines):
            if "Traceback" in line:
                # Take everything from this point to start of non-error content
                error_section = []
                for j in range(i, len(lines)):
                    current_line = lines[j]
                    error_section.append(current_line)
                    if (
                        current_line.strip() == ""
                        and j + 1 < len(lines)
                        and lines[j + 1].strip()
                        and not any(
                            marker in lines[j + 1]
                            for marker in ["Error in rule", "MissingOutputException"]
                        )
                    ):
                        break

                return "\n".join(error_section)

        return ""  # No traceback found

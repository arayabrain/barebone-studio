import logging
import logging.config
import os
import re
import shutil
import traceback
from glob import glob
from typing import List

import yaml

from studio.app.common.core.utils.filepath_creater import (
    create_directory,
    join_filepath,
)
from studio.app.const import CELLMASK_SUFFIX, TC_SUFFIX
from studio.app.dir_path import DIRPATH
from studio.app.expdb_dir_path import EXPDB_DIRPATH


class ExpDbDirMigration:
    LOGGER_NAME = None

    def __init__(self):
        self.__init_logger()

    def __init_logger(self):
        logging_config_file = join_filepath(
            [DIRPATH.CONFIG_DIR, "logging.expdb_migration.yaml"]
        )
        logging_config = yaml.safe_load(
            open(logging_config_file, encoding="utf-8").read()
        )

        log_file = (
            logging_config.get("handlers", {}).get("rotating_file", {}).get("filename")
        )
        log_dir = os.path.dirname(log_file)
        create_directory(log_dir)

        logging.config.dictConfig(logging_config)

        self.logger_ = logging.getLogger(__class__.LOGGER_NAME)

    def __move_files(self, dest_dir: str, files: List[str]):
        create_directory(dest_dir)

        self.logger_.info(f"Moving following files to {dest_dir}")

        for f in files:
            self.logger_.info(f)
            shutil.move(f, dest_dir)

        self.logger_.info(f"Moved {len(files)} files.")

    def __migrate(self):
        subject_dirs = [
            p
            for p in glob(join_filepath([EXPDB_DIRPATH.EXPDB_DIR, "M*/"]))
            if re.search(r"M\d{6}/", p)
        ]

        for subject_dir in subject_dirs:
            subject_dir = subject_dir.rstrip("/")
            subject_id = os.path.basename(subject_dir)
            self.logger_.info(f"Subject: {subject_id}")

            experiment_dirs = glob(join_filepath([subject_dir, f"{subject_id}_*/"]))

            for experiment_dir in experiment_dirs:
                experiment_dir = experiment_dir.rstrip("/")
                experiment_id = os.path.basename(experiment_dir)
                self.logger_.info(f"Experiment: {experiment_id}")

                preprocess_files = []
                for suffix in [CELLMASK_SUFFIX, TC_SUFFIX]:
                    preproccess_file = join_filepath(
                        [experiment_dir, f"{experiment_id}_{suffix}.mat"]
                    )
                    if os.path.exists(preproccess_file):
                        preprocess_files.append(preproccess_file)
                if len(preprocess_files) > 0:
                    self.__move_files(
                        join_filepath([experiment_dir, "preprocess"]), preprocess_files
                    )
                else:
                    self.logger_.info("No preprocess files found")

                orimap_files = (
                    glob(join_filepath([experiment_dir, f"{experiment_id}_dir_*.tif"]))
                    + glob(
                        join_filepath([experiment_dir, f"{experiment_id}_ori_*.tif"])
                    )
                    + glob(join_filepath([experiment_dir, f"{experiment_id}_FOV.tif"]))
                )

                if len(orimap_files) > 0:
                    self.__move_files(
                        join_filepath([experiment_dir, "preprocess", "orimaps"]),
                        orimap_files,
                    )
                else:
                    self.logger_.info("No orimap files found")

    def run_migration(self):
        self.logger_.info("Start migration.")

        try:
            self.__migrate()

        except Exception as e:
            self.logger_.error("%s: %s\n%s", type(e), e, traceback.format_exc())
        finally:
            self.logger_.info("Migration finished.")


if __name__ == "__main__":
    migrator = ExpDbDirMigration()
    migrator.run_migration()

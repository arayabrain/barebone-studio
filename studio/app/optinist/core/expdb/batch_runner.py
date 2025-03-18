import datetime
import glob
import logging
import logging.config
import os
import pathlib
import traceback
from enum import Enum

import yaml
from lauda import stopwatch
from zc import lockfile

from studio.app.common.core.users.crud_organizations import get_organization
from studio.app.common.db.database import session_scope
from studio.app.dir_path import DIRPATH
from studio.app.expdb_dir_path import EXPDB_DIRPATH
from studio.app.optinist.core.expdb.batch_unit import ExpDbBatch
from studio.app.optinist.core.expdb.crud_cells import bulk_insert_cells
from studio.app.optinist.core.expdb.crud_configs import summarize_experiment_metadata
from studio.app.optinist.core.expdb.crud_expdb import (
    create_experiment,
    get_experiment,
    update_experiment,
)
from studio.app.optinist.schemas.expdb.experiment import (
    ExpDbExperimentCreate,
    ExpDbExperimentUpdate,
)

LOCKFILE_NAME = "process.lock"
FLAG_FILE_EXT = ".proc"


class ProcessCommand(Enum):
    REGIST = "regist"
    REGIST_METADATA = "regist_metadata"
    DELETE = "delete"


class ProcessResult:
    def __init__(self):
        self.success_ids_ = []
        self.failure_ids_ = []

    @property
    def success_ids(self):
        return self.success_ids_

    @property
    def failure_ids(self):
        return self.failure_ids_

    @property
    def total_ids(self):
        return self.success_ids_ + self.failure_ids_

    def has_error(self) -> bool:
        return len(self.failure_ids_) > 0


class ExpDbBatchRunner:
    LOGGER_NAME = None  # Note: use root logger (empty name)

    def __init__(self, organization_id: int):
        self.start_time = datetime.datetime.now()
        self.__init_logger()
        self.org_id = organization_id

    def __init_logger(self):
        logging_config_file = DIRPATH.CONFIG_DIR + "/logging.expdb_batch.yaml"
        logging_config = yaml.safe_load(
            open(logging_config_file, encoding="utf-8").read()
        )

        # ログ出力先フォルダ生成（初回のみの処理）
        # ※ logging.config.dictConfig() の前に実施必要
        log_file = (
            logging_config.get("handlers", {}).get("rotating_file", {}).get("filename")
        )
        log_dir = os.path.dirname(log_file) if log_file else None
        if log_dir and (not os.path.isdir(log_dir)):
            os.mkdir(log_dir)

        logging.config.dictConfig(logging_config)

        self.logger_ = logging.getLogger(__class__.LOGGER_NAME)

    def __stopwatch_callback(watch, function=None):
        logging.getLogger(__class__.LOGGER_NAME).info(
            "processing done. [%s()][elapsed_time: %.6f sec]",
            (function.__name__ if function is not None else "(N/A)"),
            watch.elapsed_time,
        )

    @stopwatch(callback=__stopwatch_callback)
    def process(self):
        self.logger_.info("process start.")

        processResult = ProcessResult()
        error: Exception = None

        try:
            # 前処理
            self.__process_preprocess()

            # メイン処理（データ管理・解析処理処理）
            processResult = self.__process_datasets()

            # 後処理
            self.__process_postprocess()

        except lockfile.LockError:
            None  # do nothing.

        except Exception as e:
            self.logger_.error("%s: %s\n%s", type(e), e, traceback.format_exc())
            error = e

        finally:
            # 処理終了ログ出力
            if error is None:
                if processResult.has_error():
                    self.logger_.warning(
                        (
                            "process finish. [status: warning]"
                            "[success: %d][failure: %d][failure_ids: %s]"
                        ),
                        len(processResult.success_ids),
                        len(processResult.failure_ids),
                        processResult.failure_ids,
                    )
                else:
                    self.logger_.info(
                        "process finish. [status: success][total: %d]",
                        len(processResult.total_ids),
                    )
            else:
                self.logger_.info("process finish. [status: error (suspended)]")

    def __process_preprocess(self):
        """
        前処理
        """

        # ----------------------------------------
        # 2重起動防止処理（lockfile チェック）
        #
        # - ライブラリ(zc.lockfile)を利用
        # - ライブラリにより、以下の処理が担われる
        #   - lockfileの存在チェックと生成処理
        #     - lockfileの存在チェック時は、実際にプロセス(pid)が存在するかも判定される
        #   - lockfileの後処理
        #     - lockfileは残るが、プロセス(pid)の存在判定との組み合わせにより、ロックの残存は回避される
        # ----------------------------------------

        # lockfile チェック
        try:
            self.lock = lockfile.LockFile(LOCKFILE_NAME)
            # validate organization_id
            with session_scope() as db:
                get_organization(db, self.org_id)
        except lockfile.LockError as e:
            self.logger_.error("already running. - %s", e)
            raise e

    def __process_postprocess(self):
        """
        後処理
        """

        # Note: ロックファイル解除は、ライブラリ(zc.lockfile)により自動処理される
        self.lock.close()

    @stopwatch(callback=__stopwatch_callback)
    def __process_datasets(self) -> ProcessResult:
        """
        メイン処理（データ管理・解析処理処理）
        """

        processResult = ProcessResult()

        target_flag_files = self.__search_target_datasets()

        # 処理対象datasetsが存在しない場合は、ここで処理終了（return）
        if len(target_flag_files) == 0:
            self.logger_.info("No datasets found.")
            return processResult

        # 処理対象datasets検索：フラグファイルを走査
        for flag_file in target_flag_files:
            exp_id = self.__get_exp_id_from_flag_file(flag_file)
            self.logger_.info(
                "start process dataset: [exp_id: %s][flag_file: %s]", exp_id, flag_file
            )
            self.start_time = datetime.datetime.now()

            error: Exception = None

            # フラグファイル read
            with open(flag_file) as cfile:
                config = yaml.safe_load(cfile)

            # 対象データフォルダ存在チェック
            # データが存在しない場合はエラー扱いとし、次のデータ処理へスキップ

            # コマンド判定
            try:
                command = config.get("command") if config is not None else None

                if command == ProcessCommand.REGIST.value:
                    self.__process_dataset_registration(flag_file)
                elif command == ProcessCommand.REGIST_METADATA.value:
                    self.__process_dataset_metadata_registration(flag_file)
                elif command == ProcessCommand.DELETE.value:
                    self.__process_dataset_deletion(flag_file)
                else:
                    raise ValueError(
                        f"invalid command: [exp_id: {exp_id}][command: {command}]"
                    )

                processResult.success_ids.append(exp_id)

            except Exception as e:
                self.logger_.error("%s: %s\n%s", type(e), e, traceback.format_exc())
                error = e

                processResult.failure_ids.append(exp_id)

            finally:
                self.__process_dataset_postprocess(flag_file, command, error)

                if error:
                    self.logger_.error("finish process dataset: [exp_id: %s]", exp_id)
                else:
                    self.logger_.info("finish process dataset: [exp_id: %s]", exp_id)

        # datasets処理完了後の後処理:
        with session_scope() as db:
            # Summarize experiment metadata.
            summarize_experiment_metadata(db)

        return processResult

    @stopwatch(callback=__stopwatch_callback)
    def __search_target_datasets(self) -> list:
        """
        処理対象datasets検索
        """
        self.logger_.info("path: %s", EXPDB_DIRPATH.EXPDB_DIR)

        # フラグファイル検索
        target_flag_files = sorted(
            glob.glob(EXPDB_DIRPATH.EXPDB_DIR + "/*/*" + FLAG_FILE_EXT)
        )

        return target_flag_files

    def __get_exp_id_from_flag_file(self, flag_file: str) -> str:
        return os.path.basename(flag_file).split(".", 1)[0]

    @stopwatch(callback=__stopwatch_callback)
    def __process_dataset_registration(self, flag_file: str) -> bool:
        """
        Dataset登録処理
        """

        self.logger_.info("process dataset registration: %s", flag_file)
        exp_id = self.__get_exp_id_from_flag_file(flag_file)
        expdb_batch = ExpDbBatch(exp_id, self.org_id)

        with session_scope() as db:
            expdb_batch.cleanup_exp_record(db)
            db.commit()

            # Analyze & Plotting
            if expdb_batch.raw_path.microscope_file is None:
                # 顕微鏡データがない場合、以下の処理をスキップ
                self.logger_.warn("No microscope data found. Skip preprocessing.")
            else:
                stack = expdb_batch.preprocess()
                expdb_batch.generate_orimaps(stack)
                cnmf_info = expdb_batch.cell_detection_cnmf(stack)
                del stack

            stat_data = expdb_batch.generate_statdata()
            expdb_batch.generate_cellmasks()
            expdb_batch.generate_pixelmaps()
            expdb_batch.generate_plots(stat_data=stat_data)
            expdb_batch.generate_plots_using_cnmf_info(
                stat_data=stat_data, cnmf_info=cnmf_info
            )

            # Read metadata
            (attributes, view_attributes) = expdb_batch.load_exp_metadata()

            expdb_batch.save_nwb(attributes["metadata"]["metadata"])

            exp = create_experiment(
                db,
                ExpDbExperimentCreate(
                    experiment_id=exp_id,
                    organization_id=self.org_id,
                    attributes=attributes,
                    view_attributes=view_attributes,
                ),
            )

            bulk_insert_cells(db, exp.id, stat_data)

        return True

    @stopwatch(callback=__stopwatch_callback)
    def __process_dataset_metadata_registration(self, flag_file: str) -> bool:
        """
        Metadata 登録処理
        """

        self.logger_.info("process dataset metadata registration: %s", flag_file)
        exp_id = self.__get_exp_id_from_flag_file(flag_file)
        expdb_batch = ExpDbBatch(exp_id, self.org_id)

        with session_scope() as db:
            try:
                expdb_experiment = get_experiment(db, exp_id, self.org_id)
            except AssertionError:
                log = (
                    "No experiment found. skip metadata registration."
                    f" [org_id: {self.org_id}][exp_id: {exp_id}]"
                )
                self.logger_.warning(log)
                raise FileNotFoundError(log)

            # Read metadata
            (attributes, view_attributes) = expdb_batch.load_exp_metadata()

            update_experiment(
                db,
                expdb_experiment.id,
                ExpDbExperimentUpdate(
                    attributes=attributes,
                    view_attributes=view_attributes,
                ),
            )

        return True

    @stopwatch(callback=__stopwatch_callback)
    def __process_dataset_deletion(self, flag_file: str) -> bool:
        """
        Dataset削除処理
        """

        self.logger_.info("process dataset registration: %s", flag_file)
        exp_id = self.__get_exp_id_from_flag_file(flag_file)
        expdb_batch = ExpDbBatch(exp_id, self.org_id)

        with session_scope() as db:
            expdb_batch.cleanup_exp_record(db)

        return True

    def __process_dataset_postprocess(
        self, flag_file: str, command: str, error: Exception = None
    ) -> bool:
        """
        Dataset後処理
        """

        # ----------------------------------------
        # 後処理
        # - フラグファイル処理（ログ出力、リネーム）
        # ----------------------------------------

        # フラグファイル書き込みデータ作成
        if not error:
            result_log = {
                "command": command,
                "start_time": self.start_time,
                "complete_time": datetime.datetime.now(),
                "result": "success",
                "log": "completed successfully.",
            }
        else:
            result_log = {
                "command": command,
                "start_time": self.start_time,
                "complete_time": datetime.datetime.now(),
                "result": "error",
                "log": "{}: {}".format(type(error), str(error)),
            }

        # フラグファイル内容アップデート
        with open(flag_file, "w") as yf:
            yaml.dump(result_log, yf)

        # フラグファイル名作成
        if not error:
            renamed_flag_file = flag_file + ".done"
        else:
            renamed_flag_file = flag_file + ".error"

        # 過去のフラグファイルが存在する場合はリネーム
        if os.path.isfile(renamed_flag_file):
            ps = pathlib.Path(renamed_flag_file).stat()
            st_mtime = datetime.datetime.fromtimestamp(ps.st_mtime).strftime(
                "%Y%m%d%H%M%S"
            )
            os.rename(renamed_flag_file, renamed_flag_file + "." + st_mtime)

        # フラグファイルリネーム
        os.rename(flag_file, renamed_flag_file)

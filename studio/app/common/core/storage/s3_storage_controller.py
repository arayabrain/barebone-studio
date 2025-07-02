import os
import re
from subprocess import CalledProcessError

import aioboto3

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.storage.remote_storage_controller import (
    BaseRemoteStorageController,
    StorageOptionType,
)
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.dir_path import DIRPATH

logger = AppLogger.get_logger()


class S3StorageController(BaseRemoteStorageController):
    """
    S3 Storage Controller
    """

    def __init__(self, bucket_name: str):
        # init s3 bucket attributes
        assert bucket_name, "S3 bucket name is not defined."
        self.__s3_storage_bucket = bucket_name
        self.__s3_storage_url = f"s3://{bucket_name}"
        logger.debug(f"Init S3StorageController: {bucket_name=}")

    def __get_s3_client(self):
        return aioboto3.Session().client("s3")

    def __get_s3_resource(self):
        return aioboto3.Session().resource("s3")

    def _make_input_data_local_path(self, workspace_id: str, filename: str) -> str:
        input_data_local_path = join_filepath(
            [DIRPATH.INPUT_DIR, workspace_id, filename]
        )
        return input_data_local_path

    def _make_input_data_remote_path(self, workspace_id: str, filename: str) -> str:
        input_data_remote_path = join_filepath(
            [__class__.S3_INPUT_DIR, workspace_id, filename]
        )
        return input_data_remote_path

    def _make_experiment_local_path(self, workspace_id: str, unique_id: str) -> str:
        experiment_local_path = join_filepath(
            [DIRPATH.OUTPUT_DIR, workspace_id, unique_id]
        )
        return experiment_local_path

    def _make_experiment_remote_path(self, workspace_id: str, unique_id: str) -> str:
        experiment_remote_path = join_filepath(
            [__class__.S3_OUTPUT_DIR, workspace_id, unique_id]
        )
        return experiment_remote_path

    @property
    def bucket_name(self) -> str:
        return self.__s3_storage_bucket

    async def create_bucket(self) -> bool:
        """
        Note:
        - About public access settings for bucket
            - Public access permission by ACL is not allowed after 2023/4.
                - https://aws.amazon.com/jp/about-aws/whats-new/2022/12/
                    amazon-s3-automatically-enable-block-public-access-disable-
                    access-control-lists-buckets-april-2023/
            - The above requires that public access be configured via bucket policy.
        """

        create_config = {
            "LocationConstraint": os.environ.get("AWS_DEFAULT_REGION"),
        }

        async with self.__get_s3_client() as __s3_client:
            await __s3_client.create_bucket(
                Bucket=self.bucket_name,
                CreateBucketConfiguration=create_config,
            )

        logger.info(f"S3 bucket was successfully created. [{self.bucket_name}]")

        return True

    async def delete_bucket(self, force_delete=False) -> str:
        async with self.__get_s3_resource() as __s3_resource:
            bucket = await __s3_resource.Bucket(self.bucket_name)

            if force_delete:
                await bucket.objects.all().delete()

            await bucket.delete()

        logger.info(f"S3 bucket was successfully deleted. [{self.bucket_name}]")

        return True

    async def download_input_data(self, workspace_id: str, filename: str) -> bool:
        # make paths
        input_data_local_path = self._make_input_data_local_path(workspace_id, filename)
        input_data_remote_path = self._make_input_data_remote_path(
            workspace_id, filename
        )

        if os.path.isfile(input_data_local_path):
            logger.debug(f"skip download input data: {input_data_remote_path}")

        logger.debug(
            "download input data from remote storage (S3). [%s] [%s -> %s]",
            self.bucket_name,
            input_data_remote_path,
            input_data_local_path,
        )

        # ----------------------------------------
        # exec downloading
        # ----------------------------------------

        async with self.__get_s3_client() as __s3_client:
            # request s3 list_objects
            s3_list_objects = await __s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=input_data_remote_path
            )

            # check copy source object
            if not s3_list_objects or s3_list_objects.get("KeyCount", 0) == 0:
                logger.warning(
                    "remote data is not exists. [%s] [%s]",
                    self.bucket_name,
                    input_data_remote_path,
                )
                return False

            # do download data from remote storage
            target_files_count = len(s3_list_objects["Contents"])
            for index, s3_object in enumerate(s3_list_objects["Contents"]):
                s3_file_path = s3_object["Key"]
                file_size = s3_object["Size"]

                logger.debug(
                    f"download data from S3 [{self.bucket_name}] "
                    f"({index+1}/{target_files_count}) "
                    f"{s3_file_path} ({file_size:,} bytes)"
                )

                await __s3_client.download_file(
                    self.bucket_name, s3_file_path, input_data_local_path
                )

                logger.debug(
                    f"finish download data from S3 [{self.bucket_name}] "
                    f"{s3_file_path}"
                )

        return True

    async def upload_input_data(self, workspace_id: str, filename: str) -> bool:
        # make paths
        input_data_local_path = self._make_input_data_local_path(workspace_id, filename)
        input_data_remote_path = self._make_input_data_remote_path(
            workspace_id, filename
        )

        logger.debug(
            "upload data to remote storage (S3). [%s] [%s -> %s]",
            self.bucket_name,
            input_data_local_path,
            input_data_remote_path,
        )

        # ----------------------------------------
        # exec uploading
        # ----------------------------------------

        file_size = os.path.getsize(input_data_local_path)

        logger.debug(
            f"upload data to S3 [{self.bucket_name}] "
            f"{input_data_remote_path} ({file_size:,} bytes)"
        )

        async with self.__get_s3_client() as __s3_client:
            await __s3_client.upload_file(
                input_data_local_path, self.bucket_name, input_data_remote_path
            )

        logger.debug(
            f"finish upload data from S3 [{self.bucket_name}] "
            f"{input_data_remote_path}"
        )

        return True

    async def delete_input_data(self, workspace_id: str, filename: str) -> bool:
        # make paths
        input_data_remote_path = self._make_input_data_remote_path(
            workspace_id, filename
        )

        logger.debug(
            "delete input data from remote storage (s3). [%s]",
            input_data_remote_path,
        )

        # ----------------------------------------
        # exec deleting
        # ----------------------------------------

        async with self.__get_s3_resource() as __s3_resource:
            bucket = await __s3_resource.Bucket(self.bucket_name)

            objects_to_delete = bucket.objects.filter(Prefix=input_data_remote_path)
            keys_to_delete = [{"Key": obj.key} async for obj in objects_to_delete]

            if keys_to_delete:
                await bucket.delete_objects(Delete={"Objects": keys_to_delete})

        return True

    async def download_all_experiments_metas(self, workspace_ids: list = None) -> bool:
        # Whether to use AWS CLI to download user metadata
        USE_AWS_CLI_FOR_DOWNLOADING = (
            False  # Currently fixed as False (aws cli is not used)
        )

        if USE_AWS_CLI_FOR_DOWNLOADING:
            self.__download_all_experiments_metas_via_aws_cli()
        else:
            await self.__download_all_experiments_metas_via_boto3(workspace_ids)

    async def __download_all_experiments_metas_via_boto3(
        self, workspace_ids: list = None
    ) -> bool:
        """
        Download experiments metadata (yaml files) from S3

        # Specifications
        - Scan the directory structure on S3 below and download only the metadata files.
          - Structure of data storage on S3
            - bucket1
              - outputs/
                - workspace1
                  - experiment1
                    - experiment.yaml
                    - workflow.yaml
                    - ...
                  - experiment2
                  - ...
                - workspace2
                - ...
            - bucket2
            - ...
        """

        # Search workspaces directories listing on S3
        async with self.__get_s3_client() as __s3_client:
            workspaces_response = await __s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{__class__.S3_OUTPUT_DIR}/",
                Delimiter="/",
            )

        if "CommonPrefixes" not in workspaces_response:
            logger.warning(
                "No workspaces dirs found in S3 "
                f"[{self.bucket_name}][{__class__.S3_OUTPUT_DIR}]"
            )
            return False

        # Extract workspace directory listing
        all_workspaces_dirs = [
            v["Prefix"] for v in workspaces_response["CommonPrefixes"]
        ]

        # filter target workspaces_dirs
        if workspace_ids:
            re_ids = "|".join(workspace_ids)
            re_ids = f"({re_ids})"
            workspaces_dirs = [
                w for w in all_workspaces_dirs if re.search(f"/{re_ids}/$", w)
            ]
        else:
            workspaces_dirs = all_workspaces_dirs

        logger.debug(
            "download all medata from remote storage (s3). [%s] workspaces: %s",
            self.bucket_name,
            workspaces_dirs,
        )

        metadata_filenames = [
            DIRPATH.EXPERIMENT_YML,
            DIRPATH.SNAKEMAKE_CONFIG_YML,
            DIRPATH.WORKFLOW_YML,
        ]

        # Scan workspaces directories
        async with self.__get_s3_client() as __s3_client:
            for workspace_dir in workspaces_dirs:
                # Search experiments directories listing on S3
                experiments_response = await __s3_client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=workspace_dir, Delimiter="/"
                )

                if "CommonPrefixes" not in experiments_response:
                    "No experiments dirs found in S3"
                    f"[{self.bucket_name}][{workspace_dir}]"
                    continue

                # Extract experiments directory listing
                experiments_dirs = [
                    v["Prefix"] for v in experiments_response["CommonPrefixes"]
                ]
                logger.debug(
                    "Processing experiments dirs: "
                    f"[{self.bucket_name}] {experiments_dirs}"
                )

                # Scan experiments directories
                for experiment_dir in experiments_dirs:
                    # Download metadata files
                    for metadata_filename in metadata_filenames:
                        file_remote_path = experiment_dir + metadata_filename
                        flie_local_path = os.path.join(
                            DIRPATH.DATA_DIR, experiment_dir, metadata_filename
                        )

                        if not os.path.isfile(flie_local_path):
                            try:
                                # create local directory
                                os.makedirs(
                                    os.path.dirname(flie_local_path), exist_ok=True
                                )

                                # download file
                                logger.debug(
                                    f"Downloading from S3 [{self.bucket_name}]"
                                    f"[{file_remote_path} -> {flie_local_path}]"
                                )
                                await __s3_client.download_file(
                                    self.bucket_name,
                                    file_remote_path,
                                    flie_local_path,
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to download [{self.bucket_name}]"
                                    f"[{file_remote_path}]: {e}"
                                )
                        else:
                            logger.debug(f"skip download: {file_remote_path}")
                            continue

        return True

    async def __download_all_experiments_metas_via_aws_cli(self) -> bool:
        """
        NOTE:
          - この処理（config yaml files の S3 からのダウンロード）では、
            ダウンロード対象ファイルリストの取得に、python module (boto3) ではなく、
            外部コマンド (aws cli) を利用している
          - aws cli を利用する事由
            1. boto3 では、取得対象のファイルリストの Server(AWS) Side でのfilterをサポートしていない（2024.7時点）
                - 「Prefix配下のファイルリストをすべて取得 → Client Side でのFilter」の操作手順となる
            2. また 1. の操作を行う場合、Pagination の考慮も必要となる
          - 上記のため、ファイルリストの取得には、aws cli (`aws s3 sync`) を利用する形式を、この関数では用意している
            - `aws s3 sync` の利用により、特定のファイルのみのfilterが、簡潔に利用可能となる
            - しかし実際には、`aws s3 sync` も内部で Client Side でのFilter を行っている様であるため、性能面の課題は残る
            - 最終的には、 S3 APIでsyncオプションが用意され、boto3 でfilterを実現可能となることが望ましい
        """

        # ----------------------------------------
        # make paths
        # ----------------------------------------

        import subprocess
        import tempfile

        target_files = []
        with tempfile.TemporaryDirectory() as tempdir:
            """
            # CLI Command Description
            - Use `aws s3 sync`
                - Specify --dryrun to get file list (no actual sync)
            - search target files
                - Experiment Metadata Files
                    - DIRPATH.EXPERIMENT_YML
                    - DIRPATH.WORKFLOW_YML
            - command result (stdout) format
                > (dryrun) download: s3://{FILE_URL} to {DOWNLOAD_LOCAL_PATH}
                > ... (repeat above)
            """
            aws_s3_sync_command = (
                f"aws s3 sync {self.__s3_storage_url} {tempdir} "
                "--dryrun --exclude '*' "
                f"--include '*/{DIRPATH.EXPERIMENT_YML}' "
                f"--include '*/{DIRPATH.SNAKEMAKE_CONFIG_YML}' "
                f"--include '*/{DIRPATH.WORKFLOW_YML}' "
            )

            # run aws cli command
            try:
                cmd_ret = subprocess.run(
                    aws_s3_sync_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=True,
                    env={
                        "PATH": os.environ.get("PATH"),
                        "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
                        "AWS_SECRET_ACCESS_KEY": os.environ.get(
                            "AWS_SECRET_ACCESS_KEY"
                        ),
                        "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION"),
                    },
                )

                assert (
                    cmd_ret.returncode == 0
                ), f"Fail aws_s3_sync_command. {cmd_ret.stderr}"

            except CalledProcessError as e:
                logger.error(e)
                logger.error(e.stderr)
                raise e

            # extract target files paths from command's stdout
            if len(str(cmd_ret.stdout).strip()) > 0:
                target_files_str = re.sub(
                    "^.*(s3://[^ ]*) .*$", r"\1", cmd_ret.stdout, flags=(re.MULTILINE)
                ).strip()
                target_files = target_files_str.split("\n")
            else:
                target_files = []

            logger.debug(
                "aws s3 sync result: [returncode:%d][len:%d]",
                cmd_ret.returncode,
                len(target_files),
            )

        logger.debug(
            "download all medata from remote storage (s3). [%s] [count: %d]",
            self.bucket_name,
            len(target_files),
        )

        # ----------------------------------------
        # exec downloading
        # ----------------------------------------

        # do copy data from remote storage
        async with self.__get_s3_client() as __s3_client:
            target_files_count = len(target_files)
            for index, remote_config_yml_abs_path in enumerate(target_files):
                relative_config_yml_path = remote_config_yml_abs_path.replace(
                    f"{self.__s3_storage_url}/", ""
                )
                remote_config_yml_path = relative_config_yml_path
                local_config_yml_path = f"{DIRPATH.DATA_DIR}/{relative_config_yml_path}"
                local_config_yml_dir = os.path.dirname(local_config_yml_path)

                if not os.path.isfile(local_config_yml_path):
                    logger.debug(
                        f"copy config_yml: {relative_config_yml_path} "
                        f"({index+1}/{target_files_count})"
                    )

                    os.makedirs(local_config_yml_dir, exist_ok=True)

                    # do download config file
                    await __s3_client.download_file(
                        self.bucket_name,
                        remote_config_yml_path,
                        local_config_yml_path,
                    )

                else:
                    logger.debug(
                        f"skip copy config_yml: {relative_config_yml_path} "
                        f"({index+1}/{target_files_count})"
                    )
                    continue

        return True

    async def download_experiment(self, workspace_id: str, unique_id: str) -> bool:
        # make paths
        experiment_local_path = self._make_experiment_local_path(
            workspace_id, unique_id
        )
        experiment_remote_path = self._make_experiment_remote_path(
            workspace_id, unique_id
        )

        logger.debug(
            "download data from remote storage (S3). [%s] [%s -> %s]",
            self.bucket_name,
            experiment_local_path,
            experiment_remote_path,
        )

        # ----------------------------------------
        # exec downloading
        # ----------------------------------------

        async with self.__get_s3_client() as __s3_client:
            # request s3 list_objects
            s3_list_objects = await __s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=experiment_remote_path
            )

            # check copy source directory
            if not s3_list_objects or s3_list_objects.get("KeyCount", 0) == 0:
                logger.warning(
                    "remote data is not exists. [%s] [%s]",
                    self.bucket_name,
                    experiment_remote_path,
                )
                return False

            # cleaning data from local path
            if os.path.isdir(experiment_local_path):
                await self._clear_local_experiment_data(experiment_local_path)

            # do download data from remote storage
            target_files_count = len(s3_list_objects["Contents"])
            for index, s3_object in enumerate(s3_list_objects["Contents"]):
                s3_file_path = s3_object["Key"]
                file_size = s3_object["Size"]

                # skip directory on s3
                if s3_file_path.endswith("/"):
                    continue

                # make paths
                local_abs_path = os.path.join(
                    os.path.dirname(DIRPATH.OUTPUT_DIR), s3_file_path
                )
                local_abs_dir = os.path.dirname(local_abs_path)

                logger.debug(
                    f"download data from S3 [{self.bucket_name}] "
                    f"({index+1}/{target_files_count}) "
                    f"{s3_file_path} ({file_size:,} bytes)"
                )

                # create local directory before downloading
                if not os.path.exists(local_abs_dir):
                    os.makedirs(local_abs_dir)

                # do download experiment files
                await __s3_client.download_file(
                    self.bucket_name, s3_file_path, local_abs_path
                )

        return True

    async def upload_experiment(
        self, workspace_id: str, unique_id: str, target_files: list = None
    ) -> bool:
        # make paths
        experiment_local_path = self._make_experiment_local_path(
            workspace_id, unique_id
        )
        experiment_remote_path = self._make_experiment_remote_path(
            workspace_id, unique_id
        )

        logger.debug(
            "upload data to remote storage (S3). [%s] [%s -> %s]",
            self.bucket_name,
            experiment_local_path,
            experiment_remote_path,
        )

        # ----------------------------------------
        # exec uploading
        # ----------------------------------------

        # make target files path list
        # 1) Obtain target file path in absolute path format.
        target_abs_paths = []
        if target_files:  # Target specified files.
            target_abs_paths = [f"{experiment_local_path}/{f}" for f in target_files]
        else:  # Target all files.
            for root, dirs, files in os.walk(experiment_local_path):
                for filename in files:
                    local_abs_path = os.path.join(root, filename)
                    target_abs_paths.append(local_abs_path)

        # make target files path list
        # 2) Obtain target file path in transfer format to S3.
        adjusted_target_files = []
        for local_abs_path in target_abs_paths:
            local_relative_path = os.path.relpath(local_abs_path, experiment_local_path)

            s3_file_path = join_filepath(
                [
                    __class__.S3_OUTPUT_DIR,
                    workspace_id,
                    unique_id,
                    local_relative_path,
                ]
            )

            file_size = os.path.getsize(local_abs_path)
            adjusted_target_files.append([local_abs_path, s3_file_path, file_size])

        # do upload data to remote storage
        async with self.__get_s3_client() as __s3_client:
            target_files_count = len(adjusted_target_files)
            for index, (local_abs_path, s3_file_path, file_size) in enumerate(
                adjusted_target_files
            ):
                logger.debug(
                    f"upload data to S3 [{self.bucket_name}] "
                    f"({index+1}/{target_files_count}) "
                    f"{s3_file_path} ({file_size:,} bytes)"
                )

                # do upload experiment files
                await __s3_client.upload_file(
                    local_abs_path, self.bucket_name, s3_file_path
                )

        return True

    async def delete_experiment(self, workspace_id: str, unique_id: str) -> bool:
        # make paths
        experiment_remote_path = self._make_experiment_remote_path(
            workspace_id, unique_id
        )

        logger.debug(
            "delete data from remote storage (s3). [%s] [%s]",
            self.bucket_name,
            experiment_remote_path,
        )

        # ----------------------------------------
        # exec deleting
        # ----------------------------------------

        # do delete data from remote storage
        async with self.__get_s3_resource() as __s3_resource:
            bucket = await __s3_resource.Bucket(self.bucket_name)

            objects_to_delete = bucket.objects.filter(Prefix=experiment_remote_path)
            keys_to_delete = [{"Key": obj.key} async for obj in objects_to_delete]

            if keys_to_delete:
                await bucket.delete_objects(Delete={"Objects": keys_to_delete})

        return True

    async def delete_workspace(
        self, workspace_id: str, category: StorageOptionType
    ) -> bool:
        try:
            logger.info(
                f"[S3]Delete workspace '{workspace_id}' for category '{category.value}'"
            )

            # Validate category
            if category not in [
                StorageOptionType.OUTPUT,
                StorageOptionType.INPUT,
            ]:
                logger.error(f"Invalid category specified: {category.value}")
                return False

            prefix = f"{category.value}/{workspace_id}/"

            async with self.__get_s3_resource() as s3_resource:
                bucket = await s3_resource.Bucket(self.bucket_name)
                objects_to_delete = bucket.objects.filter(Prefix=prefix)
                keys_to_delete = [{"Key": obj.key} async for obj in objects_to_delete]

                if keys_to_delete:
                    await bucket.delete_objects(Delete={"Objects": keys_to_delete})
                    logger.info(f"[S3] Deleted S3 objects under prefix: {prefix}")
                else:
                    logger.warning(f"[S3] No objects found for prefix: {prefix}")

            return True

        except Exception as e:
            logger.error(f"[S3] Failed to delete workspace: {e}", exc_info=True)
            return False

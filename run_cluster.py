import argparse
import shutil
import tempfile
from pathlib import Path

from snakemake.api import (
    DeploymentMethod,
    DeploymentSettings,
    OutputSettings,
    ResourceSettings,
    SnakemakeApi,
    StorageSettings,
)

from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.dir_path import DIRPATH


def main(args):
    # Create temporary directory for isolated execution
    # Using temp directory in case of rw permission issues
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_workdir = Path(temp_dir)

        print(f"Temporary work directory created at: {temp_workdir}")

        # Copy config file to temp directory if provided
        if args.config is not None:
            if args.config.endswith(".yml") or args.config.endswith(".yaml"):
                # User provided a file path
                if not Path(args.config).exists():
                    raise FileNotFoundError(f"Config file not found: {args.config}")
                tmp_config_path = join_filepath(
                    [str(temp_workdir), DIRPATH.SNAKEMAKE_CONFIG_YML]
                )
                shutil.copyfile(args.config, tmp_config_path)
                print(f"Config file copied from {args.config} to {tmp_config_path}")
            else:
                print("Please enter config file path")

            print(f"Config file copied to temporary directory: {temp_workdir}")

        # Determine deployment methods
        deployment_methods = []
        deployment_methods.append(DeploymentMethod.CONDA)

        # Use new SnakemakeApi pattern
        with SnakemakeApi(
            OutputSettings(
                verbose=True,
                show_failed_logs=True,
            ),
        ) as snakemake_api:
            workflow_api = snakemake_api.workflow(
                snakefile=Path(DIRPATH.SNAKEMAKE_FILEPATH),
                workdir=temp_workdir,
                storage_settings=StorageSettings(),
                resource_settings=ResourceSettings(cores=args.cores),
                deployment_settings=DeploymentSettings(
                    deployment_method=deployment_methods,
                    conda_frontend="conda",
                    conda_prefix=DIRPATH.SNAKEMAKE_CONDA_ENV_DIR,
                ),
            )

            dag_api = workflow_api.dag()

            try:
                dag_api.execute_workflow()
                print("Workflow execution completed successfully")
                return True
            except Exception as e:
                print(f"Workflow execution failed: {e}")
                return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="optinist")
    parser.add_argument("--cores", type=int, default=2)
    parser.add_argument("--config", type=str, default=None)

    main(parser.parse_args())

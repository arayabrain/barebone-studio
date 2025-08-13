import argparse
import shutil
import tempfile
from pathlib import Path

from snakemake.api import (
    DAGSettings,
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
    # Temp dir for snakemake config in case of permission errors on cluster.
    # Output files saved to config file path
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_workdir = Path(temp_dir)
        print(f"Temporary work directory created at: {temp_workdir}")

        config_file_path = None

        if args.config is None:
            raise FileNotFoundError(
                "Please provide snakemake file path --config='my/path/snakemake.yaml'"
            )

        else:
            if not (args.config.endswith(".yml") or args.config.endswith(".yaml")):
                config_file_path = join_filepath(
                    [args.config, DIRPATH.SNAKEMAKE_CONFIG_YML]
                )
            else:
                config_file_path = args.config
            if not Path(config_file_path).exists():
                raise FileNotFoundError(f"Config file not found: {args.config}")

            shutil.copyfile(
                config_file_path,
                join_filepath([str(temp_workdir), "snakemake.yaml"]),
            )
            print(f"Config file copied from {config_file_path} to {temp_workdir}")

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

            dag_settings = DAGSettings(
                forceall=args.forceall,
            )

            dag_api = workflow_api.dag(
                dag_settings=dag_settings,
            )

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
    parser.add_argument(  # Default true, use --no-forceall to disable forceall
        "--forceall", default=True, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(  # Default true, use --no-use_conda to disable conda usage
        "--use_conda", default=True, action=argparse.BooleanOptionalAction
    )
    parser.add_argument("--config", type=str, default=None)

    main(parser.parse_args())

import argparse
import os
import shutil
import tempfile
from pathlib import Path

from snakemake import snakemake

from studio.app.common.core.experiment.experiment import ExptOutputPathIds
from studio.app.common.core.utils.config_handler import ConfigReader
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.dir_path import DIRPATH


def main(args):
    # Temp dir for snakemake config in case of permission errors on cluster.
    # Output files saved to config file path
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_workdir = Path(temp_dir)
        print(f"Temporary work directory created at: {temp_workdir}")

        config_file_path = None
        temp_config_file_path = None

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

            temp_config_file_path = join_filepath(
                [str(temp_workdir), Path(config_file_path).name]
            )

            shutil.copyfile(config_file_path, temp_config_file_path)

            print(
                f"Config file copied from {config_file_path} to {temp_config_file_path}"
            )

        # Main snakemake execution
        snakemake_args = {
            "snakefile": DIRPATH.SNAKEMAKE_FILEPATH,
            "forceall": args.forceall,
            "cores": args.cores,
            "use_conda": args.use_conda,
            "workdir": f"{os.path.dirname(DIRPATH.STUDIO_DIR)}",
        }

        if config_file_path is not None:
            snakemake_args["configfiles"] = [str(temp_config_file_path)]

        if args.use_conda:
            snakemake_args["conda_prefix"] = DIRPATH.SNAKEMAKE_CONDA_ENV_DIR

        print(f"Snakemake arguments: {snakemake_args}")

        try:
            result = snakemake(**snakemake_args)

            if result:
                print("snakemake execution succeeded.")
                # Copy config file back to output directory for future reference
                try:
                    # Find the output directory from the last_output in config
                    config_data = ConfigReader.read(config_file_path)
                    if config_data and "last_output" in config_data:
                        # Extract the last output path
                        last_output_path = config_data["last_output"][0]
                        # Construct absolute path and extract directory
                        absolute_output_path = join_filepath(
                            [DIRPATH.OUTPUT_DIR, last_output_path]
                        )
                        # Extract the workspace_id and unique_id
                        path_ids = ExptOutputPathIds(
                            os.path.dirname(absolute_output_path)
                        )

                        # Create the output directory path to copy the config file
                        output_config_dir = join_filepath(
                            [
                                DIRPATH.OUTPUT_DIR,
                                path_ids.workspace_id,
                                path_ids.unique_id,
                            ]
                        )
                        os.makedirs(output_config_dir, exist_ok=True)
                        output_config_path = join_filepath(
                            [output_config_dir, DIRPATH.SNAKEMAKE_CONFIG_YML]
                        )

                        shutil.copyfile(config_file_path, output_config_path)
                        print(
                            f"Config copied to output directory: {output_config_path}"
                        )
                    else:
                        print(
                            "Warning: No output path found in config, "
                            "skipping config copy"
                        )
                except Exception as e:
                    print(f"Warning: Failed to copy config to output directory: {e}")
            else:
                print("snakemake execution failed.")
                print("Check for errors above in the snakemake output.")

        except Exception as e:
            print(f"snakemake execution failed with exception: {e}")
            import traceback

            print("Full traceback:")
            traceback.print_exc()
            result = False

        return result


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

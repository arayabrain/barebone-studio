import argparse
import os
import shutil
import tempfile
from pathlib import Path

from snakemake import snakemake

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
                join_filepath([str(temp_workdir), str(Path(config_file_path).name)]),
            )
            print(f"Config file copied from {config_file_path} to {temp_workdir}")

        snakemake_args = {
            "snakefile": DIRPATH.SNAKEMAKE_FILEPATH,
            "forceall": args.forceall,
            "cores": args.cores,
            "use_conda": args.use_conda,
            "workdir": f"{os.path.dirname(DIRPATH.STUDIO_DIR)}",
        }

        if config_file_path is not None:
            snakemake_args["configfiles"] = [str(config_file_path)]

        if args.use_conda:
            snakemake_args["conda_prefix"] = DIRPATH.SNAKEMAKE_CONDA_ENV_DIR

        print(f"Snakemake arguments: {snakemake_args}")

        result = snakemake(**snakemake_args)

        if result:
            print("snakemake execution succeeded.")
        else:
            print("snakemake execution failed.")

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

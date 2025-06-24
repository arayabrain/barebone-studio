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

        if args.config is not None:
            if args.config.endswith(".yml") or args.config.endswith(".yaml"):
                if not Path(args.config).exists():
                    raise FileNotFoundError(f"Config file not found: {args.config}")
                config_file_path = join_filepath(
                    [str(temp_workdir), DIRPATH.SNAKEMAKE_CONFIG_YML]
                )
                shutil.copyfile(args.config, config_file_path)
                print(f"Config file copied from {args.config} to {config_file_path}")
            else:
                print(f"Please provide a valid YAML config file, got: {args.config}")

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

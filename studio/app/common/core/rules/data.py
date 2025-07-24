# flake8: noqa
# Exclude from lint for the following reason
# This file is executed by snakemake and cause the following lint errors
# - E402: sys.path.append is required to import optinist modules
# - F821: do not import snakemake
import sys
from os.path import abspath, dirname

ROOT_DIRPATH = dirname(dirname(dirname(dirname(dirname(dirname(abspath(__file__)))))))
sys.path.append(ROOT_DIRPATH)

from studio.app.common.core.logger import AppLogger

logger = AppLogger.get_logger()


def main():
    try:
        import os

        from studio.app.common.core.rules.file_writer import FileWriter
        from studio.app.common.core.snakemake.smk_utils import SmkUtils
        from studio.app.common.core.snakemake.snakemake_reader import RuleConfigReader
        from studio.app.common.core.utils.pickle_handler import PickleWriter
        from studio.app.common.core.workflow.workflow import NodeType, NodeTypeUtil
        from studio.app.const import FILETYPE

        logger.info(f"=== DATA RULE DEBUG INFO ===")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Snakemake config keys: {list(snakemake.config.keys())}")
        logger.info(f"Snakemake params: {snakemake.params}")
        logger.info(
            f"Environment variables: AWS_BATCH_JOB_ID={os.environ.get('AWS_BATCH_JOB_ID')}"
        )

        last_output = snakemake.config["last_output"]

        logger.info(f"Reading rule config for: {snakemake.params.name}")
        rule_config = RuleConfigReader.read(snakemake.params.name)

        logger.info(f"Resolving NWB file reference...")
        rule_config = SmkUtils.resolve_nwbfile_reference(rule_config)

        if NodeTypeUtil.check_nodetype_from_filetype(rule_config.type) == NodeType.DATA:
            if rule_config.type in [FILETYPE.IMAGE]:
                rule_config.input = snakemake.input
            else:
                rule_config.input = snakemake.input[0]
        else:
            assert False, f"Invalid rule type: {rule_config.type}"

        rule_config.output = snakemake.output[0]

        outputfile = None
        if rule_config.type in [FILETYPE.CSV, FILETYPE.BEHAVIOR]:
            outputfile = FileWriter.csv(rule_config, rule_config.type)
        elif rule_config.type == FILETYPE.IMAGE:
            outputfile = FileWriter.image(rule_config)
        elif rule_config.type == FILETYPE.HDF5:
            outputfile = FileWriter.hdf5(rule_config)
        elif rule_config.type == FILETYPE.MATLAB:
            outputfile = FileWriter.mat(rule_config)
        elif rule_config.type == FILETYPE.MICROSCOPE:
            outputfile = FileWriter.microscope(rule_config)
        else:
            assert False, f"Invalid file type: {rule_config.type}"

        PickleWriter.write(rule_config.output, outputfile)

    except Exception as e:
        logger.error(AppLogger.format_exc_traceback(e))


if __name__ == "__main__":
    main()

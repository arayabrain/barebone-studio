import os

from studio.app.common.core.utils.config_handler import ConfigReader, ConfigWriter
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.filepath_finder import find_param_filepath
from studio.app.dir_path import DIRPATH

dirpath = DIRPATH.OUTPUT_DIR
filename = "test.yaml"


def test_config_reader():
    filename = "eta"
    filepath = find_param_filepath(filename)
    config = ConfigReader.read(filepath)

    assert isinstance(config, dict)
    assert len(config) > 0

    filename = "not_exist_config"
    filepath = find_param_filepath(filename)
    config = ConfigReader.read(filepath)

    assert isinstance(config, dict)
    assert len(config) == 0


def test_config_writer():
    filepath = join_filepath([dirpath, filename])

    if os.path.exists(filepath):
        os.remove(filepath)

    ConfigWriter.write(dirpath, filename, {"test": "test"})

    assert os.path.exists(filepath)

import os

from studio.services.dir_path import DIRPATH
from studio.services.pickle.pickle_writer import PickleWriter

filepath = f"{DIRPATH.OPTINIST_DIR}/output/0123/func2/func2.pkl"


def test_PickleWriter():
    PickleWriter.write(
        filepath,
        "abc",
    )

    assert os.path.exists(filepath)
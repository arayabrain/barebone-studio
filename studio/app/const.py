from pydantic.dataclasses import dataclass


@dataclass
class FILETYPE:
    IMAGE: str = "image"
    CSV: str = "csv"
    HDF5: str = "hdf5"
    BEHAVIOR: str = "behavior"


ACCEPT_TIFF_EXT = [".tif", ".tiff", ".TIF", ".TIFF"]
ACCEPT_CSV_EXT = [".csv"]
ACCEPT_HDF5_EXT = [".hdf5", ".nwb", ".HDF5", ".NWB"]

FUNC_KEY = "function"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

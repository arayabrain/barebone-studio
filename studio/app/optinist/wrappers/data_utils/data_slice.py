# data_slice.py
# import numpy as np

from studio.app.common.core.logger import AppLogger
from studio.app.optinist.dataclass.fluo import FluoData


def data_slice(
    data: FluoData,
    output_dir: str,
    params: dict = None,
    **kwargs,
) -> dict():
    """
    Slices fluorescence data based on provided indices.

    Parameters:
        data (FluoData): Fluorescence data to slice.
        output_dir (str): Directory to save the output data.
        params (dict): Parameters containing slice information.
        **kwargs: Additional keyword arguments.

    Returns:
        dict: A dictionary containing the sliced data.
    """
    logger = AppLogger.get_logger()
    logger.info("Starting data slicing processing")

    # Get slicing parameters
    start = params.get("start", 0) if params else 0
    end = params.get("end", None) if params else None
    axis = params.get("axis", 0) if params else 0

    # Create slicing indices
    if axis == 0:
        if end:
            sliced_data_array = data.data[start:end]
        else:
            sliced_data_array = data.data[start:]
    else:  # axis == 1
        if end:
            sliced_data_array = data.data[:, start:end]
        else:
            sliced_data_array = data.data[:, start:]

    # Create FluoData object
    sliced_data = FluoData(sliced_data_array, file_name="sliced_data")

    # Return the sliced data
    output = {
        "data": sliced_data,
    }

    logger.info("Completed data slicing processing")
    return output

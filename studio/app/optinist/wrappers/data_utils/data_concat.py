# data_concat.py
import numpy as np

from studio.app.common.core.logger import AppLogger
from studio.app.optinist.dataclass.fluo import FluoData


def data_concat(
    data1: FluoData,
    data2: FluoData,
    output_dir: str,
    params: dict = None,
    **kwargs,
) -> dict():
    """
    Concatenates two fluorescence data arrays.

    Parameters:
        data1 (FluoData): First fluorescence data.
        data2 (FluoData): Second fluorescence data.
        output_dir (str): Directory to save the output data.
        params (dict): Optional parameters with axis specification.
        **kwargs: Additional keyword arguments.

    Returns:
        dict: A dictionary containing the concatenated data.
    """
    logger = AppLogger.get_logger()
    logger.info("Starting data concatenation processing")

    # Get axis parameter, default to 0
    axis = params.get("axis", 0) if params else 0

    # Concatenate the data
    concatenated_data = FluoData(
        np.concatenate([data1.data, data2.data], axis=axis),
        file_name="concatenated_data",
    )

    # Return the concatenated data
    output = {
        "data": concatenated_data,
    }

    logger.info("Completed data concatenation processing")
    return output

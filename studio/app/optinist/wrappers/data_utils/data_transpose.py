import numpy as np

from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass.base import BaseData
from studio.app.optinist.wrappers.data_utils.data_utils_utils import return_as_data_type


def data_transpose(
    data: BaseData,
    output_dir: str,
    params: dict = None,
    **kwargs,
) -> dict(transposed_data=BaseData):
    """
    Transposes data dimensions according to the specified permutation.

    Parameters:
        data (BaseData): Input data to transpose. Can be one of several types:
                         BehaviorData, CsvData, FluoData, ImageData, or RoiData.
        output_dir (str): Directory to save the output data.
        params (dict, optional): 'transpose_dims': List of indices specifying the new
                                dimension order.
    Returns:
        transposed_data: A dictionary containing the transposed data with a key
        that corresponds to appropriate data type.
    """
    logger = AppLogger.get_logger()
    logger.info("Starting data transposition")

    # Get dimension permutation from parameters
    dims = params.get("transpose_dims", None) if params else None

    logger.debug(f"Params type: {type(dims).__name__}")
    logger.debug(f"Dims value: {dims}")

    try:
        raw_data = data.data
        ndim = raw_data.ndim
    except Exception as e:
        logger.error(f"Unable to access data: {str(e)}")
        raise ValueError(
            f"Input data doesn't have accessible .data attribute: {str(e)}"
        )

    # Set default permutation if none provided
    if dims is None:
        logger.warning("No dimension permutation provided, using default transpose")
        # For 2D data, use simple transpose
        if ndim == 2:
            dims = [1, 0]
        # For higher dimensions, just use identity (no change)
        else:
            dims = list(range(ndim))
    else:
        if isinstance(dims, str):
            dims = [int(d.strip()) for d in dims.split(",")]
        elif isinstance(dims, list):
            dims = [int(d) if isinstance(d, str) else d for d in dims]

    # Validate dims against data dimensions
    if len(dims) != ndim:
        raise ValueError(
            f"Dimension mismatch: data has {ndim} dimensions but {len(dims)} specified"
        )

    logger.info(f"Applying dimension permutation: {dims}")

    try:
        # Transpose the data
        tp_data = np.transpose(raw_data, dims)
        file_name = (
            f"transposed_{data.file_name}"
            if hasattr(data, "file_name")
            else "transposed_data"
        )

        # Use utility function to return the correct data type
        typed_result = return_as_data_type(data, tp_data, output_dir, file_name)
        data_object = list(typed_result.values())[0]
        typed_result["transposed_data"] = data_object

        return {"transposed_data": data_object}

        # info = {}
        # typed_data_dict = return_as_data_type(data, tp_data, output_dir, file_name)
        # info.update(typed_data_dict)

        # return info

    except Exception as e:
        logger.error(f"Error during data transposition: {str(e)}")
        raise ValueError(f"Data transposition failed: {str(e)}")

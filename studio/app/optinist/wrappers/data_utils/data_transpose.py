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
    Transposes data dimensions according to specified permutation.

    Parameters:
        data (BaseData): Input data to transpose. Can be one of several types:
                         BehaviorData, CsvData, FluoData, ImageData, or RoiData.
        output_dir (str): Directory to save the output data.
        params (dict, optional): Dictionary containing transpose specifications:
                        - 'transpose_dims': List or comma-separated string specifying
                            dimension permutation for transpose operation.
                            Examples:
                            - "1, 0": Simple 2D transpose (swap rows/columns)
                            - "1,0,2": String format for rotating 3D data
                            - If None, defaults to simple transpose for 2D data
                                or return un-transposed for higher dimensions

    Returns:
        dict: A dictionary containing the transposed data with preserved metadata
              and proper data type conversion.
    """
    logger = AppLogger.get_logger()
    logger.info("Starting data transposition")

    # Get dimension permutation from parameters
    dims = params.get("transpose_dims", None) if params else None

    if dims is not None:
        if isinstance(dims, str):
            dims = [int(d.strip()) for d in dims.split(",")]
        elif isinstance(dims, list):
            dims = [int(d) if isinstance(d, str) else d for d in dims]

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
        if ndim == 2:
            # For 2D data, use simple transpose
            dims = [1, 0]
        else:
            # For higher dimensions, just use identity (no change)
            dims = list(range(ndim))
    else:
        if isinstance(dims, str):
            dims = [int(d.strip()) for d in dims.split(",")]
        elif isinstance(dims, list):
            dims = [int(d) if isinstance(d, str) else d for d in dims]

    # Validate dimensions
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
        logger.info(f"Input data shape: {raw_data.shape}")
        logger.info(f"Transposed data shape: {tp_data.shape}")

        # Use utility function to return the correct data type
        output_data = return_as_data_type(data, tp_data, output_dir, file_name)
        return output_data

    except Exception as e:
        logger.error(f"Error during data transposition: {str(e)}")
        raise ValueError(f"Data transposition failed: {str(e)}")

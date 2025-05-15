import numpy as np

from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.csv import CsvData
from studio.app.common.dataclass.image import ImageData
from studio.app.optinist.dataclass.behavior import BehaviorData
from studio.app.optinist.dataclass.fluo import FluoData
from studio.app.optinist.dataclass.roi import RoiData


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
        dict: A dictionary containing the transposed data with a key that corresponds to
              appropriate data type.
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
        # Set output based on data type
        if isinstance(data, BehaviorData):
            transposed_data = BehaviorData(
                data=tp_data,
                std=data.std if hasattr(data, "std") else None,
                index=data.index if hasattr(data, "index") else None,
                params=params,
                file_name=file_name,
            )
            logger.info(f"Transposed behavior data to dims: {dims}")
            return {"behaviors_data": transposed_data}

        elif isinstance(data, CsvData):
            transposed_data = CsvData(
                data=tp_data,
                params=params or {},
                file_name=file_name,
                meta=data.meta if hasattr(data, "meta") else None,
            )
            logger.info(f"Transposed csv data to dims: {dims}")
            return {"behaviors_data": transposed_data}

        elif isinstance(data, FluoData):
            transposed_data = FluoData(
                data=tp_data,
                std=data.std if hasattr(data, "std") else None,
                index=data.index if hasattr(data, "index") else None,
                params=params,
                cell_numbers=data.cell_numbers
                if hasattr(data, "cell_numbers")
                else None,
                file_name=file_name,
                meta=data.meta if hasattr(data, "meta") else None,
            )
            logger.info(f"Transposed neural data to dims: {dims}")
            return {"neural_data": transposed_data}

        elif isinstance(data, ImageData):
            transposed_data = ImageData(
                data=tp_data,
                output_dir=output_dir,
                file_name=file_name,
                meta=data.meta if hasattr(data, "meta") else None,
            )
            logger.info(f"Transposed image data to dims: {dims}")
            return {"image": transposed_data}

        elif isinstance(data, RoiData):
            transposed_data = RoiData(
                data=tp_data,
                output_dir=output_dir,
                file_name=file_name,
                meta=data.meta if hasattr(data, "meta") else None,
            )
            logger.info(f"Transposed roi data to dims: {dims}")
            return {"roi": transposed_data}

        else:
            # Generic approach for other data types
            logger.warning(
                f"Using generic approach for data type: {type(data).__name__}"
            )
            try:
                if hasattr(data, "meta"):
                    transposed_data = type(data)(
                        data=tp_data, file_name=file_name, meta=data.meta
                    )
                else:
                    transposed_data = type(data)(data=tp_data, file_name=file_name)
                return {"transposed_data": transposed_data}

            except TypeError as e:
                logger.error(f"Unable to create transposed data object: {str(e)}")
                raise ValueError(
                    f"Cannot transpose object of type {type(data).__name__}: {str(e)}"
                )

    except Exception as e:
        logger.error(f"Error during data transposition: {str(e)}")
        raise ValueError(f"Data transposition failed: {str(e)}")

import numpy as np

from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.csv import CsvData
from studio.app.common.dataclass.image import ImageData
from studio.app.optinist.dataclass.behavior import BehaviorData
from studio.app.optinist.dataclass.fluo import FluoData
from studio.app.optinist.dataclass.iscell import IscellData
from studio.app.optinist.dataclass.roi import RoiData
from studio.app.optinist.wrappers.data_utils.data_utils_utils import return_as_data_type


def data_concat(
    data1: BaseData,
    data2: BaseData,
    output_dir: str,
    params: dict = None,
    **kwargs,
) -> dict(concatenated_data=BaseData):
    """
    Concatenates two data arrays along specified axis.

    Parameters:
        data1 (BaseData): First data array to concatenate. Accepts several types:
                    BehaviorData, CsvData, FluoData, ImageData, IscellData, RoiData.
        data2 (BaseData): Second data array to concatenate. Accepts same types.
                    Must be compatible with data1 for concatenation along specified axis
        output_dir (str): Directory to save the output data.
        params (dict, optional): Dictionary containing concatenation specifications:
                    - 'axis': Axis along which to concatenate
                    - 'output_type': Optional output type specification
                        (behaviors_data, neural_data, image_data, iscell_data, roi_data)
                        If not specified, will be inferred from data1 type
                    - 'time_axis': Specified or determined by data type
                    - 'std_method': How to handle standard deviation:
                        * "concatenate": concatenate existing std arrays
                        * "compute": compute new std for concatenated data
                        * "none": no std in output
                    - 'std_axis': If std_method="compute",
                        which axis to compute std along (default: time_axis)

    Returns:
        dict: A dictionary containing the concatenated data with appropriate data type.
    """
    logger = AppLogger.get_logger()
    logger.info("Starting data concatenation")

    # Get parameters with defaults based on data type
    default_params = determine_default_params(data1)

    axis = params.get("axis", None) if params else None
    axis = int(axis) if axis is not None and str(axis).strip() else None
    if axis is None:
        axis = default_params["axis"]
        logger.info(
            f"Using default axis {axis} for {type(data1).__name__} concatenation"
        )
    else:
        logger.info(f"Concatenation axis specified: {axis}")

    time_axis = params.get("time_axis", None) if params else None
    time_axis = (
        int(time_axis) if time_axis is not None and str(time_axis).strip() else None
    )
    if time_axis is None:
        time_axis = default_params["time_axis"]
        logger.info(f"Using default time_axis {time_axis} for {type(data1).__name__}")
    else:
        logger.info(f"Time axis specified: {time_axis}")
    time_axis = int(time_axis)

    std_method = params.get("std_method", None) if params else None
    if std_method is None:
        std_method = default_params["std_method"]
    else:
        std_method = std_method.strip().lower()
        if std_method not in ["concatenate", "compute", "none"]:
            logger.warning(f"Invalid std_method '{std_method}'.")
            logger.warning(
                "Expected std_method values: 'concatenate', 'compute', or 'none'."
            )
        else:
            logger.info(f"Std method specified: {std_method}")

    std_axis = params.get("std_axis", None) if params else None
    std_axis = int(std_axis) if std_axis is not None and str(std_axis).strip() else None
    if std_axis is None:
        std_axis = default_params["std_axis"]
    else:
        logger.info(f"Std axis specified: {std_axis}")
    std_axis = int(std_axis)

    output_type = params.get("output_type", None) if params else None
    if output_type is not None and output_type != "":
        output_type = output_type.strip().lower()
        logger.info(f"Output type specified: {output_type}")
    else:
        logger.info("Output type unspecified, using same type as input data 1")

    try:
        data1_array = data1.data
        data2_array = data2.data
        # Get the raw data arrays

        logger.info(
            f"Data1 shape: {data1_array.shape}, Data2 shape: {data2_array.shape}"
        )

        # Validate axis parameter
        if axis >= data1_array.ndim or axis < -data1_array.ndim:
            raise ValueError(
                f"Axis {axis} is out of bounds for {data1_array.ndim}D array"
            )

        # Validate basic compatibility
        if data1_array.ndim != data2_array.ndim:
            raise ValueError(
                f"Cannot concat arrays of dims:{data1_array.ndim} & {data2_array.ndim}"
            )

        # Try concatenation and let NumPy handle compatibility
        try:
            concatenated_array = np.concatenate([data1_array, data2_array], axis=axis)
            logger.info(f"Concatenated data shape: {concatenated_array.shape}")
        except ValueError as concat_error:
            # Provide more helpful error message with shape information
            raise ValueError(
                f"Cannot concat arrays of shape:{data1_array.shape}&{data2_array.shape}"
                f"along axis {axis}. NumPy error: {str(concat_error)}"
            )

        # Handle index concatenation based on time_axis
        concatenated_index = None
        if (
            hasattr(data1, "index")
            and hasattr(data2, "index")
            and data1.index is not None
            and data2.index is not None
        ):
            if axis == time_axis:
                # Concatenating along time dimension - concatenate indices
                concatenated_index = np.concatenate([data1.index, data2.index])
                logger.info("Concatenated time indices")
            else:
                # Use data1's index (should be same for non-time concatenation)
                concatenated_index = data1.index
                logger.info("Used data1 index")
        elif hasattr(data1, "index") and data1.index is not None:
            concatenated_index = data1.index
        elif hasattr(data2, "index") and data2.index is not None:
            concatenated_index = data2.index

        # Handle std based on std_method
        concatenated_std = None

        if std_method == "concatenate":
            if (
                hasattr(data1, "std")
                and hasattr(data2, "std")
                and data1.std is not None
                and data2.std is not None
            ):
                try:
                    concatenated_std = np.concatenate([data1.std, data2.std], axis=axis)
                    logger.info("Concatenated existing std arrays")
                except Exception as e:
                    logger.warning(f"Could not concatenate std arrays: {e}")

        elif std_method == "compute":
            try:
                # For timeseries data, we need std to have the same shape as data
                if concatenated_array.ndim == 2:
                    # Don't reduce dimensions - use broadcasting to maintain shape
                    axis_std = np.std(concatenated_array, axis=std_axis, keepdims=True)
                    concatenated_std = np.broadcast_to(
                        axis_std, concatenated_array.shape
                    )
                    logger.info(f"Computed std with shape {concatenated_std.shape}")
                else:
                    concatenated_std = np.std(concatenated_array, axis=std_axis)
                    logger.info(f"Computed new std along axis {std_axis}")
            except Exception as e:
                logger.warning(f"Could not compute std: {e}")

        # Create output data object
        file_name = (
            f"concatenated_{data1.file_name}"
            if hasattr(data1, "file_name")
            else "concatenated_data"
        )
        output_data = return_as_data_type(
            data1,  # Use data1 as template for type inference
            concatenated_array,
            output_dir,
            file_name,
            output_type=output_type,
            std=concatenated_std,
            index=concatenated_index,
        )

        data_object = list(output_data.values())[0]
        return {"concatenated_data": data_object}

    except Exception as e:
        logger.error(f"Error during data concatenation: {str(e)}")
        raise ValueError(f"Data concatenation failed: {str(e)}")


def determine_default_params(data1):
    """Determine default concatenation axis, time axis, std axis, and std method
    based on data type."""
    if isinstance(data1, ImageData):
        return {
            "axis": 0,  # Time in dim 0, concat along time dimension
            "time_axis": 0,  # Time is in dimension 0
            "std_axis": 0,  # Compute std across time
            "std_method": "compute",  # Compute new temporal statistics
        }
    elif isinstance(data1, FluoData):
        return {
            "axis": 0,  # (roi, time) shape, concat along roi dimension
            "time_axis": 1,  # Time is in dimension 1
            "std_axis": 1,  # Compute std across time for each ROI
            "std_method": "compute",  # Compute stats over combined ROI population
        }
    elif isinstance(data1, (BehaviorData, CsvData)):
        return {
            "axis": 1,  # Time in dim 0, concat along non-time dimension (features)
            "time_axis": 0,  # Time is in dimension 0
            "std_axis": 0,  # Compute std across time for each feature
            "std_method": "concatenate",  # Preserve individual feature characteristics
        }
    elif isinstance(data1, IscellData):
        return {
            "axis": 0,  # 1D data, concat along the only available dimension
            "time_axis": None,  # Safe default (ROI data typically spatial)
            "std_axis": None,  # Compute std along concatenation dimension
            "std_method": "none",  # Compute new spatial statistics
        }
    elif isinstance(data1, RoiData):
        return {
            "axis": 0,  # 1D data, concat along the only available dimension
            "time_axis": None,  # Safe default (ROI data typically spatial)
            "std_axis": None,  # Compute std along concatenation dimension
            "std_method": "none",  # Compute new spatial statistics
        }
    else:
        return {
            "axis": 0,  # Default fallback
            "time_axis": 1,  # Legacy default
            "std_axis": 1,  # Legacy default
            "std_method": "compute",  # Safest default (always works)
        }

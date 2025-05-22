import numpy as np

from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.image import ImageData
from studio.app.optinist.dataclass.fluo import FluoData
from studio.app.optinist.wrappers.data_utils.data_utils_utils import return_as_data_type


def data_slice(
    data: BaseData,
    output_dir: str,
    params: dict = None,
    **kwargs,
) -> dict(sliced_data=BaseData):
    """
    Slices data along specified dimensions.

    Parameters:
        data (BaseData): Input data to slice. Can be one of several types:
                         BehaviorData, CsvData, FluoData, ImageData, or RoiData.
        output_dir (str): Directory to save the output data.
        params (dict, optional): Dictionary containing slice specifications:
                               - 'slice_specs': List of slice specs for each dimension.
                                 Each spec can be:
                                 - Null/empty/':'/all: Keep the entire dimension
                                 - 'start:end': Range slice
                                 - 'start:step:end': Strided slice
                                 - 'squeeze': Remove this dimension (must have size 1)
                                 - integer: Single index to select (removes dimension)

    Returns:
        dict: A dictionary containing the sliced data and any derived data products.
    """
    logger = AppLogger.get_logger()
    logger.info("Starting data slicing")

    # Get slice specifications from parameters
    slice_specs = params.get("slice_dims", None) if params else None

    logger.debug(f"Data slice - User input specs: {slice_specs}")
    logger.debug(f"Data shape: {data.data.shape}")

    try:
        raw_data = data.data
        ndim = raw_data.ndim
        original_shape = raw_data.shape
        logger.info(f"Original data shape: {original_shape}")
    except Exception as e:
        logger.error(f"Unable to access data: {str(e)}")
        raise ValueError(
            f"Input data doesn't have accessible .data attribute: {str(e)}"
        )

    # Handle case where no slice specs are provided
    if slice_specs is None:
        logger.warning("No slice specifications provided, returning original data")
        return return_as_data_type(data, raw_data, output_dir, "sliced_data")

    # Convert slice_specs to list format if it's a string
    if isinstance(slice_specs, str):
        slice_specs = [s.strip() for s in slice_specs.split(",")]
    elif isinstance(slice_specs, list):
        slice_specs = [s.strip() if isinstance(s, str) else s for s in slice_specs]

    # Make sure we have specs for all dimensions
    if len(slice_specs) < ndim:
        slice_specs = slice_specs + [None] * (ndim - len(slice_specs))
    elif len(slice_specs) > ndim:
        raise ValueError(
            f"Too many slice specs provided ({len(slice_specs)} for {ndim} dimensions)"
        )

    # Process each dimension's slice specification
    index_specs = []

    for i, spec in enumerate(slice_specs):
        # Skip empty specs or "all" indicator
        if spec is None or (isinstance(spec, str) and spec.strip() in ("", ":", "all")):
            index_specs.append(slice(None))
            continue

        # Handle "squeeze" keyword for dimensions of size 1
        if isinstance(spec, str) and spec.strip() == "squeeze":
            if raw_data.shape[i] == 1:
                index_specs.append(0)  # Integer index removes dimension
            else:
                logger.warning(
                    f"Cannot squeeze dimension {i} with size {raw_data.shape[i]}"
                )
                index_specs.append(slice(None))
            continue

        # Handle integer index (removes dimension)
        if isinstance(spec, int) or (isinstance(spec, str) and spec.strip().isdigit()):
            idx = int(spec.strip() if isinstance(spec, str) else spec)
            if 0 <= idx < raw_data.shape[i]:
                # Make sure we're adding an actual integer, not a slice
                logger.debug(
                    f"Data slice - Adding integer index {idx} for dimension {i}"
                )
                index_specs.append(int(idx))  # Force conversion to int
            else:
                maxshape = raw_data.shape[i] - 1
                logger.warning(
                    f"Index {idx} out of bounds for dim {i} (max: {maxshape})"
                )
                index_specs.append(slice(None))
            continue

        # Parse slice notation (start:end or start:step:end)
        if isinstance(spec, str) and ":" in spec:
            try:
                parts = [p.strip() for p in spec.split(":")]

                if len(parts) == 2:
                    # Format: start:end
                    start = int(parts[0]) if parts[0] else None
                    end = int(parts[1]) if parts[1] else None
                    index_specs.append(slice(start, end))

                elif len(parts) == 3:
                    # Format: start:stop:step
                    start = int(parts[0]) if parts[0] else None
                    stop = int(parts[1]) if parts[1] else None
                    step = int(parts[2]) if parts[2] else None
                    index_specs.append(slice(start, stop, step))

                else:
                    logger.warning(f"Invalid slice format: {spec}")
                    index_specs.append(slice(None))

            except ValueError:
                logger.warning(f"Could not parse slice spec: {spec}")
                index_specs.append(slice(None))

            continue

        # Unrecognized specification
        logger.warning(f"Unrecognized slice spec: {spec}")
        index_specs.append(slice(None))

    logger.debug(f"Data slice - Applying indexing: {index_specs}")

    try:
        # Apply slices
        sliced_data = raw_data[tuple(index_specs)]
        logger.info(f"Result data shape: {sliced_data.shape}")

        # Create output filename
        file_name = (
            f"sliced_{data.file_name}" if hasattr(data, "file_name") else "sliced_data"
        )

        # Initialize info dictionary
        info = {}

        # Get mean timeseries (first dimension should be time)
        mean_timeseries = None
        if sliced_data.ndim == 2:
            mean_timeseries = np.mean(sliced_data, axis=1)
        elif sliced_data.ndim == 3:
            mean_timeseries = np.mean(sliced_data, axis=(1, 2))
        elif sliced_data.ndim == 4:
            mean_timeseries = np.mean(sliced_data, axis=(1, 2, 3))

        if mean_timeseries is not None:
            logger.info(f"Mean timeseries shape: {mean_timeseries.shape}")
            # Create a FluoData object for mean timeseries
            mean_ts_data = FluoData(data=mean_timeseries, file_name="mean_timeseries")
            info["mean_timeseries"] = mean_ts_data

        # Create mean image
        mean_image = None
        if sliced_data.ndim == 3:
            # Average over time dimension (axis=0)
            mean_image = np.mean(sliced_data, axis=0)
            logger.debug(f"Data slice - Mean image shape: {mean_image.shape}")
            mean_img_data = ImageData(
                data=mean_image, output_dir=output_dir, file_name="mean_image"
            )
            info["mean_image"] = mean_img_data

        # Get the properly typed data
        typed_data_dict = return_as_data_type(data, sliced_data, output_dir, file_name)
        logger.debug(
            f"Data slice - Returned data type: {type(typed_data_dict).__name__}"
        )
        info.update(typed_data_dict)
        logger.debug(f"Data slice - Info dictionary: {info}")

        if info.get("neural_data") is not None:
            Type = type(info["neural_data"]).__name__
            logger.debug(f"Data slice - info neural_data type:{Type}")
            Shape = info["neural_data"].data.shape
            logger.debug(f"Data slice - info neural_data shape: {Shape}")
        elif info.get("behaviors_data") is not None:
            Type = type(info["behaviors_data"]).__name__
            logger.debug(f"Data slice - info behaviors_data type: {Type}")
            Shape = info["behaviors_data"].data.shape
            logger.debug(f"Data slice - info behaviors_data shape: {Shape}")

        return info

    except Exception as e:
        logger.error(f"Error during data slicing: {str(e)}")
        raise ValueError(f"Data slicing failed: {str(e)}")

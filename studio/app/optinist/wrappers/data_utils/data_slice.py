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

    if slice_specs is not None:
        if isinstance(slice_specs, str):
            slice_specs = [s.strip() for s in slice_specs.split(",")]
        elif isinstance(slice_specs, list):
            slice_specs = [s.strip() if isinstance(s, str) else s for s in slice_specs]

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
        logger.info("No slice specifications provided, returning original data")
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

    logger.info(f"Data slice - Applying indexing: {index_specs}")

    try:
        # Apply slices to all parts of data
        sliced_data = raw_data[tuple(index_specs)]
        logger.info(f"Sliced data shape: {sliced_data.shape}")

        # Handle std if available
        sliced_std = None
        if hasattr(data, "std") and data.std is not None:
            try:
                # Apply the same slicing to std (assumes std has same shape as data)
                sliced_std = data.std[tuple(index_specs)]
            except Exception as std_err:
                logger.warning(f"Failed to slice std: {std_err}")
                sliced_std = None

        # Handle index
        sliced_index = None
        index_dim = None
        if hasattr(data, "index") and data.index is not None:
            original_index = data.index
            # Find which dimension matches the index length
            for dim_idx, dim_size in enumerate(original_shape):
                if dim_size == len(original_index):
                    index_dim = dim_idx
                    break

            if index_dim is not None:
                try:
                    # Apply the slice for the matching dimension
                    index_slice_spec = index_specs[index_dim]
                    sliced_index = original_index[index_slice_spec]
                except Exception as idx_err:
                    logger.warning(f"Failed to slice index: {idx_err}")
                    # Create default index for the sliced data
                    sliced_index = np.arange(
                        sliced_data.shape[-1]
                        if sliced_data.ndim > 1
                        else sliced_data.shape[0]
                    )
            else:
                # No matching dimension found, create default index
                sliced_index = np.arange(
                    sliced_data.shape[-1]
                    if sliced_data.ndim > 1
                    else sliced_data.shape[0]
                )

        # Create output filename
        file_name = (
            f"sliced_{data.file_name}" if hasattr(data, "file_name") else "sliced_data"
        )

        # Initialize info dictionary
        info = {}

        # Get mean timeseries based on the index dimension
        mean_timeseries = None
        if sliced_index is not None and index_dim is not None:
            # Calculate mean over all dimensions except the index dimension
            other_axes = tuple(i for i in range(sliced_data.ndim) if i != index_dim)

            if other_axes:  # Only if there are other dimensions to average over
                mean_timeseries = np.mean(sliced_data, axis=other_axes)
            else:
                # If only one dimension (the index dimension), use the data as is
                mean_timeseries = sliced_data

        if mean_timeseries is not None:
            # Create a FluoData object for mean timeseries with the sliced index
            mean_ts_data = FluoData(
                data=mean_timeseries, file_name="mean_timeseries", index=sliced_index
            )
            info["mean_timeseries"] = mean_ts_data

        # Create mean image for multi-dimensional data
        if sliced_data.ndim >= 3 and index_dim is not None:
            # For 3D+ data, create a spatial average (average over the time dimension)
            spatial_axes = tuple(i for i in range(sliced_data.ndim) if i != index_dim)
            if len(spatial_axes) >= 2:
                mean_image = np.mean(sliced_data, axis=index_dim)
                mean_img_data = ImageData(
                    data=mean_image, output_dir=output_dir, file_name="mean_image"
                )
                info["mean_image"] = mean_img_data

        # Create sliced data object using return_as_data_type with kwargs
        output_data = return_as_data_type(
            data,
            sliced_data,
            output_dir,
            file_name,
            std=sliced_std,
            index=sliced_index,
            output_type=None,
        )
        info.update(output_data)

        return info

    except Exception as e:
        logger.error(f"Error during data slicing: {str(e)}")
        raise ValueError(f"Data slicing failed: {str(e)}")

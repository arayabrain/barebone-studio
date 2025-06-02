from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.csv import CsvData
from studio.app.common.dataclass.image import ImageData
from studio.app.optinist.dataclass.behavior import BehaviorData
from studio.app.optinist.dataclass.fluo import FluoData
from studio.app.optinist.dataclass.iscell import IscellData
from studio.app.optinist.dataclass.roi import RoiData


def return_as_data_type(data, processed_data, output_dir, file_name, **kwargs):
    """Helper function to return the correct data type with processed data."""
    logger = AppLogger.get_logger()

    # Extract kwargs
    std = kwargs.get("std", None)
    index = kwargs.get("index", None)
    output_type = kwargs.get("output_type", None)
    if isinstance(output_type, str) and output_type.strip() == "":
        output_type = None

    logger.info(f"Input data type: {type(data).__name__}")
    if output_type is not None:
        logger.info(f"Requested output_type: {output_type}")
    else:
        logger.info("No output_type specified, using input data type for output")

    # Determine output type and key based on input type or explicit output_type
    if output_type == "behaviors_data" or (
        output_type is None and isinstance(data, (BehaviorData, CsvData))
    ):
        result = BehaviorData(
            data=processed_data,
            std=std,
            index=index,
            params={},
            file_name=file_name,
        )
        output_key = "behaviors_data"

    elif output_type == "neural_data" or (
        output_type is None and isinstance(data, FluoData)
    ):
        result = FluoData(
            data=processed_data,
            std=std,
            index=index,
            params={},
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        output_key = "neural_data"

    elif output_type == "image_data" or (
        output_type is None and isinstance(data, ImageData)
    ):
        result = ImageData(
            data=processed_data,
            output_dir=output_dir,
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        output_key = "image"

    elif output_type == "iscell_data" or (
        output_type is None and isinstance(data, IscellData)
    ):
        result = IscellData(
            data=processed_data,
            file_name=file_name,
        )
        output_key = "iscell"

    elif output_type == "roi_data" or (
        output_type is None and isinstance(data, RoiData)
    ):
        result = RoiData(
            data=processed_data,
            output_dir=output_dir,
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        output_key = "roi"

    else:
        logger.warning(f"Unknown output_type '{output_type}', defaulting to BaseData")
        result = BaseData(
            data=processed_data,
            params={},
            file_name=file_name,
        )
        output_key = "data"

    logger.debug(f"Created {type(result).__name__} with output key: {output_key}")
    return {output_key: result}

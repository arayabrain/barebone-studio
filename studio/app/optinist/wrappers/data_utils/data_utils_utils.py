from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.csv import CsvData
from studio.app.common.dataclass.image import ImageData
from studio.app.optinist.dataclass.behavior import BehaviorData
from studio.app.optinist.dataclass.fluo import FluoData
from studio.app.optinist.dataclass.roi import RoiData


def return_as_data_type(data, processed_data, output_dir, file_name, **kwargs):
    """Helper function to return the correct data type with processed data."""
    logger = AppLogger.get_logger()
    logger.debug(f"Data as type: {type(data).__name__}")
    logger.debug(f"Processed data as type: {type(processed_data).__name__}")

    # Extract kwargs
    std = kwargs.get("std", None)
    index = kwargs.get("index", None)

    if isinstance(data, BehaviorData):
        result = BehaviorData(
            data=processed_data,
            std=std,
            index=index,
            params={},
            file_name=file_name,
        )
        output_key = "behaviors_data"

    elif isinstance(data, CsvData):
        result = BehaviorData(
            data=processed_data,
            std=std,
            index=index,
            params={},
            file_name=file_name,
        )
        output_key = "behaviors_data"

    elif isinstance(data, FluoData):
        result = FluoData(
            data=processed_data,
            std=std,
            index=index,
            params={},
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        output_key = "neural_data"

    elif isinstance(data, ImageData):
        result = ImageData(
            data=processed_data,
            output_dir=output_dir,
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        output_key = "image"

    elif isinstance(data, RoiData):
        result = RoiData(
            data=processed_data,
            output_dir=output_dir,
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        output_key = "roi"

    else:
        # Generic fallback
        result = BaseData(
            data=processed_data,
            params={},
            file_name=file_name,
        )
        output_key = "data"

    logger.debug(
        f"Using output key: {output_key} for data type: {type(result).__name__}"
    )

    return {output_key: result}

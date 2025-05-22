from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass.csv import CsvData
from studio.app.common.dataclass.image import ImageData
from studio.app.optinist.dataclass.behavior import BehaviorData
from studio.app.optinist.dataclass.fluo import FluoData
from studio.app.optinist.dataclass.roi import RoiData


def return_as_data_type(data, processed_data, output_dir, file_name):
    """Helper function to return the correct data type with processed data."""
    logger = AppLogger.get_logger()
    logger.debug(f"Data as type: {type(data).__name__}")
    logger.debug(f"Processed data as type: {type(processed_data).__name__}")
    if isinstance(data, BehaviorData):
        result = BehaviorData(
            data=processed_data,
            std=data.std if hasattr(data, "std") else None,
            index=data.index if hasattr(data, "index") else None,
            params={},
            file_name=file_name,
        )
        return {"behaviors_data": result}

    elif isinstance(data, CsvData):
        result = CsvData(
            data=processed_data,
            params={},
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        return {"behaviors_data": result}

    elif isinstance(data, FluoData):
        result = FluoData(
            data=processed_data,
            std=data.std if hasattr(data, "std") else None,
            index=data.index if hasattr(data, "index") else None,
            params={},
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        return {"neural_data": result}

    elif isinstance(data, ImageData):
        result = ImageData(
            data=processed_data,
            output_dir=output_dir,
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        return {"image": result}

    elif isinstance(data, RoiData):
        result = RoiData(
            data=processed_data,
            output_dir=output_dir,
            file_name=file_name,
            meta=data.meta if hasattr(data, "meta") else None,
        )
        return {"roi": result}

    else:
        # Generic approach for other data types
        try:
            if hasattr(data, "meta"):
                result = type(data)(
                    data=processed_data, file_name=file_name, meta=data.meta
                )
            else:
                result = type(data)(data=processed_data, file_name=file_name)
            return {"sliced_data": result}
        except TypeError as e:
            raise ValueError(
                f"Cannot create sliced data for type {type(data).__name__}: {str(e)}"
            )

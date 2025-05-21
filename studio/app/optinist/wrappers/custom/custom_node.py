# -- Import standard libraries --
import numpy as np

from studio.app.common.core.experiment.experiment import ExptOutputPathIds
from studio.app.common.core.logger import AppLogger

# -- Import OptiNiSt visualization modules --
# Examples:
# from studio.app.common.dataclass import BarData, HeatMapData,
# HistogramData, ScatterData, LineData, PieData, PolarData, ScatterData
from studio.app.common.dataclass import HeatMapData, ImageData

# -- Import OptiNiSt core data modules --
# Examples:
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass import FluoData

# from typing import Dict, Literal, Union
# import pandas as pd


# from studio.app.optinist.dataclass import FluoData, BehaviorData, CaimanCnmfData,
# IscellData, LccdData, NWBFile, RoiData, SpikingActivityData, Suite2pData
# from studio.app.common.core.experiment.experiment import ExptOutputPathIds

# -- Import ROI detection modules --
# Examples:
# from studio.app.optinist.wrappers.suite2p import file_convert, registration, roi
# from studio.app.optinist.wrappers.caiman import motion_correction, cnmf
# from studio.app.optinist.wrappers.lccd import lccd_detection

# -- Import OptiNiSt analysis modules --
# Examples:
# from studio.app.optinist.wrappers.optinist.basic_neural_analysis.eta import ETA
# from studio.app.optinist.wrappers.optinist.my_custom_node import MyCustomNode

# -- Import visualization modules --
# from caiman.utils.visualization import local_correlations
# from plotly.subplots import make_subplots
# import plotly.graph_objects as go
# import plotly.express as px

logger = AppLogger.get_logger()


def my_function(
    # Required inputs
    neural_data: ImageData,  # Fluorescence data from previous processing
    output_dir: str,  # Directory to save output files
    # Optional inputs
    # iscell: IscellData = None,  # Cell classification data if needed
    params: dict = None,  # Additional parameters to customize processing
    **kwargs  # Catch-all for additional arguments
    # Function returns a dictionary containing all outputs
) -> dict(fluo=FluoData, image=ImageData, heatmap=HeatMapData):
    """Example template for creating analysis functions.

    This function shows the basic structure for creating analysis functions
    that work with the pipeline, including proper input handling, NWB file
    creation, and return format.

    Args:
        neural_data: Fluorescence data from previous processing steps
        output_dir: Directory where output files should be saved
        iscell: Optional cell classification data
        params: Optional dictionary of parameters to customize processing
        **kwargs: Additional keyword arguments

    Returns:
        dict: Dictionary containing all output data and metadata
    """

    # 1. Set up logging if needed
    function_id = ExptOutputPathIds(output_dir).function_id
    logger.info(f"start my_function: {function_id}")

    # 2. Get additional data from kwargs if needed
    # nwbfile = kwargs.get("nwbfile", {})

    # 3. Set default parameters and update with user params
    default_params = {"window_size": 10, "threshold": 0.5}
    if params is not None:
        default_params.update(params)

    # 4. Main analysis code goes here
    example_fluo_data = np.random.rand(100, 20)  # Example data

    example_imaging_data = np.random.rand(10, 512, 512)

    example_processing = example_fluo_data > default_params["threshold"]

    example_analysis = np.corrcoef(example_processing)
    for i in range(example_analysis.shape[0]):
        example_analysis[i, i] = np.nan

    # 5. Prepare NWB file structure
    # Create a new NWB file dictionary or update existing one
    nwb_output = {}

    # Add ROIs if your analysis creates them
    roi_list = [{"accepted": i} for i in range(1, 5)]  # List of accepted ROIs
    roi_list.extend({"rejected": i} for i in range(6, 11))  # And rejected ROIs
    nwb_output[NWBDATASET.ROI] = {function_id: {"roi_list": roi_list}}

    # Example of adding processing results
    nwb_output[NWBDATASET.POSTPROCESS] = {
        function_id: {"data": example_analysis[0]}  # Your analysis outputs
    }

    # Example of data in column format (e.g. for classifications)
    nwb_output[NWBDATASET.COLUMN] = {
        function_id: {
            "name": "my_classification",
            "description": "Description of the classification",
            "data": example_analysis[1],
        }
    }

    # 6. Prepare return dictionary
    # This should contain all outputs and processed data
    info = {
        "fluo": FluoData(example_fluo_data, file_name="fluo"),
        "image": ImageData(
            example_imaging_data, output_dir=output_dir, file_name="image"
        ),
        "heatmap": HeatMapData(example_analysis, file_name="heatmap"),
    }

    return info

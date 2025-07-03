from studio.app.optinist.wrappers.data_utils.data_concat import data_concat
from studio.app.optinist.wrappers.data_utils.data_slice import data_slice
from studio.app.optinist.wrappers.data_utils.data_transpose import data_transpose
from studio.app.optinist.wrappers.data_utils.fluo_from_hdf5 import fluo_from_hdf5
from studio.app.optinist.wrappers.data_utils.microscope_to_img import microscope_to_img
from studio.app.optinist.wrappers.data_utils.roi_fluo_from_hdf5 import (
    roi_fluo_from_hdf5,
)
from studio.app.optinist.wrappers.data_utils.roi_from_hdf5 import roi_from_hdf5
from studio.app.optinist.wrappers.data_utils.vacant_roi import vacant_roi

utils_wrapper_dict = {
    "utils": {
        "data_concat": {
            "function": data_concat,
            "conda_name": "optinist",
        },
        "data_slice": {
            "function": data_slice,
            "conda_name": "optinist",
        },
        "data_transpose": {
            "function": data_transpose,
            "conda_name": "optinist",
        },
        "fluo_from_hdf5": {
            "function": fluo_from_hdf5,
            "conda_name": "optinist",
        },
        "roi_from_hdf5": {
            "function": roi_from_hdf5,
            "conda_name": "optinist",
        },
        "roi_fluo_from_hdf5": {
            "function": roi_fluo_from_hdf5,
            "conda_name": "optinist",
        },
        "microscope_to_img": {
            "function": microscope_to_img,
            "conda_name": "microscope",
        },
        "vacant_roi": {
            "function": vacant_roi,
            "conda_name": "optinist",
        },
    },
}

import os

import numpy as np

from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass.image import ImageData
from studio.app.optinist.dataclass.microscope_expdb import MicroscopeExpdbData
from studio.app.optinist.microscopes.MicroscopeDataReaderUtils import (
    MicroscopeDataReaderUtils,
)
from studio.app.optinist.wrappers.expdb.stack_average import stack_average
from studio.app.optinist.wrappers.expdb.stack_phase_correct import stack_phase_correct
from studio.app.optinist.wrappers.expdb.stack_register import (
    stack_register,
    stack_register_3d,
)

logger = AppLogger.get_logger()


def preprocessing(
    microscope: MicroscopeExpdbData, output_dir: str, params: dict = None, **kwargs
) -> dict(stack=ImageData):
    logger.info("start preprocessing.")

    # convert_onefileの処理を実装
    params_flatten = {}
    for segment in params.values():
        params_flatten.update(segment)
    params = params_flatten

    exp_id = os.path.basename(os.path.dirname(microscope.path))
    reader = MicroscopeDataReaderUtils.get_reader(microscope.path)
    ome_meta = reader.ome_metadata

    nwbfile = kwargs.get("nwbfile", {})
    nwbfile["imaging_plane"]["imaging_rate"] = ome_meta.imaging_rate
    nwbfile["device"]["metadata"] = ome_meta.get_ome_values()
    if reader.lab_specific_metadata is not None:
        nwbfile["device"]["lab_specific_metadata"] = reader.lab_specific_metadata
    info = {"nwbfile": {"input": nwbfile}}

    raw_stack = reader.get_image_stacks()  # (ch, t, y, x) or (ch, t, z, y, x)
    microscope.data = raw_stack
    is_timeseries = ome_meta.size_t > 1

    # set common params to variables
    first_dim = params["first_dim"]

    # run preprocess for each channel
    for ch in range(ome_meta.size_c):
        if ome_meta.size_z > 1:
            stack = raw_stack[ch].transpose(2, 3, 1, 0)  # (y, x, z, t)
        else:
            stack = raw_stack[ch].transpose(1, 2, 0)  # (y, x, t)

        if is_timeseries:
            period = params["period"]
            runs = params["runs"]

            fov = np.squeeze(stack_average(stack, period, runs))  # (y, x, (z))
            info["avg"] = ImageData(
                fov.copy(), output_dir=output_dir, file_name=f"{exp_id}_avg_ch{ch + 1}"
            )
            stack, dx = stack_phase_correct(stack, fov, first_dim)
            fov = np.squeeze(stack_average(stack, period, runs))
            info["p_avg"] = ImageData(
                fov.copy(),
                output_dir=output_dir,
                file_name=f"{exp_id}_p_avg_ch{ch + 1}",
            )

            if params["do_realign"]:
                if stack.ndim == 3:
                    usfac = params["usfac"]
                    realign_params, stack = stack_register(stack, fov, usfac)
                elif stack.ndim == 4:
                    le = params["le"]
                    shift_method = params["shift_method"]
                    realign_params, stack = stack_register_3d(
                        stack, fov, le, shift_method
                    )

                fov = np.squeeze(stack_average(stack, period, runs))
                info["rp_avg"] = ImageData(
                    fov,
                    output_dir=output_dir,
                    file_name=f"{exp_id}_rp_avg_img_ch{ch + 1}",
                )
                info["stack"] = ImageData(  # (t, y, x) or (t, z, y, x)
                    # TODO: test for 4D stack
                    (
                        stack.transpose(2, 0, 1)
                        if stack.ndim == 3
                        else stack.transpose(3, 2, 0, 1)
                    ),
                    output_dir=output_dir,
                    file_name=f"{exp_id}_realigned_stack_ch{ch + 1}",
                )

            else:
                info["stack"] = ImageData(  # (t, y, x) or (t, z, y, x)
                    # TODO: test for 4D stack
                    (
                        stack.transpose(2, 0, 1)
                        if stack.ndim == 3
                        else stack.transpose(3, 2, 0, 1)
                    ),
                    output_dir=output_dir,
                    file_name=f"{exp_id}_corrected_stack_ch{ch + 1}",
                )

        else:  # for anatomy (non-timeseries)
            info["avg"] = ImageData(
                stack.copy(),
                output_dir=output_dir,
                file_name=f"{exp_id}_avg_ch{ch + 1}",
            )
            stack, dx = stack_phase_correct(stack, stack, first_dim)
            info["p_avg"] = ImageData(
                stack,
                output_dir=output_dir,
                file_name=f"{exp_id}_p_avg_ch{ch + 1}",
            )
            info["stack"] = ImageData(
                stack,
                output_dir=output_dir,
                file_name=f"{exp_id}_corrected_stack_ch{ch + 1}",
            )

        return info

import os

from studio.app.common.core.experiment.experiment import ExptOutputPathIds
from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass import ImageData
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass import RoiData
from studio.app.optinist.wrappers.caiman.caiman_utils import CaimanUtils
from studio.app.optinist.wrappers.optinist.utils import recursive_flatten_params

logger = AppLogger.get_logger()


def caiman_mc(
    image: ImageData, output_dir: str, params: dict = None, **kwargs
) -> dict(mc_images=ImageData):
    import numpy as np
    from caiman import load_memmap, save_memmap, stop_server
    from caiman.cluster import setup_cluster
    from caiman.motion_correction import MotionCorrect
    from caiman.source_extraction.cnmf.params import CNMFParams

    function_id = ExptOutputPathIds(output_dir).function_id
    unique_id = ExptOutputPathIds(output_dir).unique_id
    logger.info(f"start caiman motion_correction: {function_id}")

    flattened_params = {}
    recursive_flatten_params(params, flattened_params)
    params = flattened_params

    # Specify a unique CAIMAN_TEMPDIR
    # *To avoid collisions of temporary files (memmap files)
    mc_unique_id = f"{unique_id}_{function_id}"
    CaimanUtils.set_caimam_byid_tempdir(mc_unique_id)

    opts = CNMFParams()

    if params is not None:
        opts.change_params(params_dict=params)

    # TODO: Add parameters for node
    n_processes = 1
    dview = None
    # This process launches another process to run the CNMF algorithm,
    # so this node use at least 2 core.
    if n_processes == 1:
        c, dview, n_processes = setup_cluster(
            backend="single", n_processes=n_processes, single_thread=True
        )
    else:
        c, dview, n_processes = setup_cluster(
            backend="multiprocessing", n_processes=n_processes
        )
    logger.info(f"n_processes: {n_processes}")

    mc = MotionCorrect(image.path, dview=dview, **opts.get_group("motion"))

    mc.motion_correct(save_movie=True)
    border_to_0 = 0 if mc.border_nan == "copy" else mc.border_to_0

    # memory mapping
    mmap_file_new = save_memmap(
        mc.mmap_file, base_name=function_id, order="C", border_to_0=border_to_0
    )
    stop_server(dview=dview)

    # now load the file
    Yr, dims, T = load_memmap(mmap_file_new)

    images = np.array(Yr.T.reshape((T,) + dims, order="F"))

    # Release variables associated with memmap files when they are no longer needed.
    # *Avoid lock errors when cleaning memmap files.
    del Yr, dims, T

    meanImg, rois = __process_images(images)

    xy_trans_data = (
        (np.array(mc.x_shifts_els), np.array(mc.y_shifts_els))
        if params["pw_rigid"]
        else np.array(mc.shifts_rig)
    )

    mc_images = ImageData(images, output_dir=output_dir, file_name="mc_images")

    nwbfile = {}
    nwbfile[NWBDATASET.MOTION_CORRECTION] = {
        function_id: {
            "mc_data": mc_images,
            "xy_trans_data": xy_trans_data,
        }
    }

    info = {
        "mc_images": mc_images,
        "meanImg": ImageData(meanImg, output_dir=output_dir, file_name="meanImg"),
        "rois": RoiData(rois, output_dir=output_dir, file_name="rois"),
        "nwbfile": nwbfile,
    }

    # Clean up temporary files
    try:
        __handle_mmap_cleanup(mc, mmap_file_new)
    except Exception as e:
        logger.error("caiman_mc: Failed to cleanup memmap files.")
        logger.error(e)

    # Clean up unique CAIMAN_TEMPDIR
    try:
        CaimanUtils.cleanup_caiman_byid_tempdir(mc_unique_id)
    except Exception as e:
        logger.error("caiman_mc: Failed to cleanup tempdir.")
        logger.error(e)

    return info


def __process_images(images):
    import numpy as np
    from caiman.base.rois import extract_binary_masks_from_structural_channel

    meanImg = images.mean(axis=0)
    rois = (
        extract_binary_masks_from_structural_channel(
            meanImg, gSig=7, expand_method="dilation"
        )[0]
        .reshape(meanImg.shape[0], meanImg.shape[1], -1)
        .transpose(2, 0, 1)
    )

    rois = rois.astype(np.float32)
    for i, _ in enumerate(rois):
        rois[i] *= i + 1

    rois = np.nanmax(rois, axis=0)
    rois[rois == 0] = np.nan
    rois -= 1
    return meanImg, rois


def __handle_mmap_cleanup(mc, mmap_file_new):
    # Explicitly gc before deleting memmap file
    # *Avoid lock errors when cleaning memmap files.
    import gc

    gc.collect()

    for mmap_file in mc.mmap_file:
        if os.path.isfile(mmap_file):
            os.remove(mmap_file)

    if os.path.isfile(mmap_file_new):
        os.remove(mmap_file_new)

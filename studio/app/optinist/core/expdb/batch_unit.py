import json
import logging
import math
import os
import shutil
from dataclasses import dataclass
from glob import glob
from typing import Optional, Tuple

import numpy as np
import scipy
import scipy.sparse
import tifffile
from lauda import stopwatch
from PIL import Image
from scipy.io import loadmat, savemat
from sqlmodel import Session

from studio.app.common.core.utils.config_handler import ConfigReader
from studio.app.common.core.utils.filepath_creater import (
    create_directory,
    join_filepath,
)
from studio.app.common.core.utils.filepath_finder import find_param_filepath
from studio.app.common.dataclass.image import ImageData
from studio.app.const import (
    ACCEPT_FILE_EXT,
    CELLMASK_FIELDNAME,
    CELLMASK_SUFFIX,
    EXP_METADATA_SUFFIX,
    FOV_CONTRAST,
    FOV_SUFFIX,
    TC_FIELDNAME,
    TC_SUFFIX,
    THUMBNAIL_HEIGHT,
    TS_SUFFIX,
)
from studio.app.expdb_dir_path import EXPDB_DIRPATH
from studio.app.optinist.core.expdb.crud_cells import bulk_delete_cells
from studio.app.optinist.core.expdb.crud_expdb import (
    delete_experiment,
    extract_experiment_view_attributes,
    get_experiment,
)
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.core.nwb.nwb_creater import save_nwb
from studio.app.optinist.dataclass import ExpDbData, StatData
from studio.app.optinist.dataclass.microscope_expdb import MicroscopeExpdbData
from studio.app.optinist.wrappers.caiman.cnmf_preprocessing import (
    caiman_cnmf_preprocessing,
    get_roi,
)
from studio.app.optinist.wrappers.expdb import analyze_stats
from studio.app.optinist.wrappers.expdb.get_orimap import get_orimap
from studio.app.optinist.wrappers.expdb.kmeans_analysis import (
    generate_kmeans_visualization,
    kmeans_analysis,
)
from studio.app.optinist.wrappers.expdb.pca_analysis import (
    generate_pca_visualization,
    pca_analysis,
)
from studio.app.optinist.wrappers.expdb.preprocessing import preprocessing
from studio.app.optinist.wrappers.optinist.utils import recursive_flatten_params


@dataclass
class Result:
    success: bool
    message: Optional[str] = None


def get_default_params(name: str):
    filepath = find_param_filepath(name)
    return ConfigReader.read(filepath)


def save_image_with_thumb(img_path: str, img):
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img)
        if img.mode == "F":
            img = img.convert("RGB")
    img.save(img_path)
    w, h = img.size
    new_width = int(w * (THUMBNAIL_HEIGHT / h))
    thumb_img = img.resize((new_width, THUMBNAIL_HEIGHT), Image.Resampling.BILINEAR)
    thumb_img.save(img_path.replace(".png", ".thumb.png"))


class ExpDbPath:
    def __init__(self, exp_id: str, is_raw=False):
        subject_id = exp_id.split("_")[0]

        if is_raw:
            self.exp_dir = join_filepath([EXPDB_DIRPATH.EXPDB_DIR, subject_id, exp_id])
            assert os.path.exists(self.exp_dir), f"exp_dir not found: {self.exp_dir}"
            self.output_dir = join_filepath([self.exp_dir, "outputs"])

            # input_files
            microscope_files = []
            for ext in ACCEPT_FILE_EXT.MICROSCOPE_EXPDB_EXT.value:
                microscope_files.extend(glob(join_filepath([self.exp_dir, f"*{ext}"])))
            self.microscope_file = (
                microscope_files[0] if len(microscope_files) > 0 else None
            )
            # NOTE: Metadata file is allowed to be missing.
            self.exp_metadata_file = join_filepath(
                [self.exp_dir, f"{exp_id}_{EXP_METADATA_SUFFIX}.json"]
            )
            self.ts_file = join_filepath([self.exp_dir, f"{exp_id}_{TS_SUFFIX}.mat"])
            assert os.path.exists(self.ts_file), f"ts_file not found: {self.ts_file}"

            # preprocess
            self.preprocess_dir = join_filepath([self.exp_dir, "preprocess"])
            self.info_file = join_filepath([self.preprocess_dir, f"{exp_id}_info.mat"])

            self.orimaps_dir = join_filepath([self.preprocess_dir, "orimaps"])
            self.fov_file = join_filepath(
                [self.orimaps_dir, f"{exp_id}_{FOV_SUFFIX}.tif"]
            )

            self.tc_file = join_filepath(
                [self.preprocess_dir, f"{exp_id}_{TC_SUFFIX}.mat"]
            )
            self.cellmask_file = join_filepath(
                [self.preprocess_dir, f"{exp_id}_{CELLMASK_SUFFIX}.mat"]
            )
        else:
            self.exp_dir = join_filepath(
                [EXPDB_DIRPATH.PUBLIC_EXPDB_DIR, subject_id, exp_id]
            )
            self.output_dir = self.exp_dir

        # outputs
        self.plot_dir = join_filepath([self.output_dir, "plots"])
        self.cellmask_dir = join_filepath([self.output_dir, "cellmasks"])
        self.pixelmap_dir = join_filepath([self.output_dir, "pixelmaps"])
        self.nwb_file = join_filepath([self.output_dir, f"{exp_id}.nwb"])


class ExpDbBatch:
    LOGGER_NAME = None  # Note: use root logger (empty name)

    def __init__(self, exp_id: str, org_id: int) -> None:
        self.logger_ = logging.getLogger(__class__.LOGGER_NAME)
        self.exp_id = exp_id
        self.org_id = org_id

        self.raw_path = ExpDbPath(self.exp_id, is_raw=True)
        self.pub_path = ExpDbPath(self.exp_id)
        self.nwb_input_config = ConfigReader.read(filepath=find_param_filepath("nwb"))
        self.nwbfile = {}
        self._configure_matplotlib()

    def __stopwatch_callback(watch, function=None):
        logging.getLogger(__class__.LOGGER_NAME).info(
            "processing done. [%s()][elapsed_time: %.6f sec]",
            (function.__name__ if function is not None else "(N/A)"),
            watch.elapsed_time,
        )

    def check_is_circular_data(self, data_name: str):
        """Check if data is circular based on patterns in filename"""
        circular_patterns = ["_ori", "_OF-PRC-", "_dot"]
        is_circular_data = any(pattern in data_name for pattern in circular_patterns)
        return is_circular_data

    @stopwatch(callback=__stopwatch_callback)
    def cleanup_exp_record(self, db: Session):
        try:
            exp = get_experiment(db, self.exp_id, self.org_id)
            bulk_delete_cells(db, exp.id)
            delete_experiment(db, exp.id)
        except AssertionError:
            pass

        # Clean up raw path
        create_directory(self.raw_path.output_dir, delete_dir=True)

        # Clean up public path if different
        if self.raw_path.output_dir != self.pub_path.output_dir:
            create_directory(self.pub_path.output_dir, delete_dir=True)

    @stopwatch(callback=__stopwatch_callback)
    def load_raw_cellmask_data(self, sparse: bool = False) -> int:
        cellmask = loadmat(self.raw_path.cellmask_file).get(CELLMASK_FIELDNAME)

        if not sparse:
            cellmask = cellmask.toarray()

        imxx, ncells = cellmask.shape
        return (cellmask, imxx, ncells)

    @stopwatch(callback=__stopwatch_callback)
    def load_raw_timecourse_data(self):
        """
        Load timecourse data from .mat file
        Returns the timecourse data array
        """
        timecourse = loadmat(self.raw_path.tc_file).get(TC_FIELDNAME)
        if timecourse is None:
            self.logger_.info(f"Failed to load timecourse from {self.raw_path.tc_file}")

        return timecourse

    @stopwatch(callback=__stopwatch_callback)
    def process_roi_masks(self):
        """
        Process cellmask data  from .mat file to create ROI image.
        Returns roi_image : ndarray
            2D composite ROI mask
        """

        cellmask_data = self.load_raw_cellmask_data(sparse=True)[0]

        # Handle sparse matrix format
        if not scipy.sparse.issparse(cellmask_data):
            self.logger_.info("Converting to sparse matrix")
            cellmask_data = scipy.sparse.csc_matrix(cellmask_data)
        else:
            self.logger_.info("Using provided sparse matrix")

        # Get dimensions from shape
        d, nr = cellmask_data.shape
        imx = imy = int(np.sqrt(d))
        dims = (imx, imy)
        self.logger_.info(f"Cellmask shape: {d}x{nr}, Image dimensions: {dims}")

        # Log matrix sparsity
        self.logger_.info(
            f"Matrix has {cellmask_data.nnz} non-zero elements out of {d*nr} total"
        )

        # Get parameters for ROI processing
        params = get_default_params("caiman_cnmf_preprocessing")
        flat_params = {}
        recursive_flatten_params(params, flat_params)
        roi_thr = flat_params.get("roi_thr", 0.9)
        thr_method = "nrg"
        swap_dim = False  # Use F-order reshaping

        # Process ROIs
        self.logger_.info("Processing ROIs with get_roi")
        roi_image_list = get_roi(cellmask_data, roi_thr, thr_method, swap_dim, dims)
        self.logger_.info(f"get_roi returned {len(roi_image_list)} ROI images")

        # Check if we have results
        if roi_image_list and len(roi_image_list) > 0:
            # Stack images
            roi_image_3d = np.stack(roi_image_list).astype(float)
            self.logger_.info(f"3D ROI shape: {roi_image_3d.shape}")

            # Process ROI images
            roi_image_3d[roi_image_3d == 0] = np.nan
            roi_image_3d = np.where(
                np.isnan(roi_image_3d), roi_image_3d, roi_image_3d - 1
            )

            # Create composite mask
            roi_image = np.nanmax(roi_image_3d, axis=0)

            # Ensure finite values
            roi_image = np.where(np.isfinite(roi_image), roi_image, np.nan)

            # Count non-NaN values
            non_nan_count = np.sum(~np.isnan(roi_image))
            self.logger_.info(f"ROI mask has {non_nan_count} non-NaN pixels")
        else:
            self.logger_.warning("No ROIs found! Creating empty array.")
            roi_image = np.full(dims, np.nan)

        return roi_image

    @stopwatch(callback=__stopwatch_callback)
    def preprocess(self) -> ImageData:
        self.logger_.info("process 'preprocess' start.")
        create_directory(self.raw_path.preprocess_dir)

        preprocess_results = preprocessing(
            microscope=MicroscopeExpdbData(self.raw_path.microscope_file),
            output_dir=self.raw_path.preprocess_dir,
            params=get_default_params("preprocessing"),
            nwbfile=self.nwb_input_config,
        )

        savemat(
            join_filepath([self.raw_path.info_file]),
            {
                k: v.data
                for k, v in preprocess_results.items()
                if isinstance(v, ImageData)
            },
        )
        self.nwb_input_config = preprocess_results["nwbfile"]["input"]

        return preprocess_results["stack"]

    @stopwatch(callback=__stopwatch_callback)
    def generate_orimaps(self, stack: ImageData):
        self.logger_.info("process 'generate_orimaps' start.")
        create_directory(self.raw_path.orimaps_dir)

        expdb = ExpDbData(paths=[self.raw_path.ts_file])
        get_orimap(
            stack=stack,
            expdb=expdb,
            output_dir=self.raw_path.orimaps_dir,
            params={**get_default_params("get_orimap"), "exp_id": self.exp_id},
        )

    @stopwatch(callback=__stopwatch_callback)
    def cell_detection_cnmf(self, stack: ImageData):
        # NOTE: frame rateなどの情報を引き渡すためにnwb_input_configを引数に与える
        self.logger_.info("process 'cell_detection_cnmf' start.")
        return caiman_cnmf_preprocessing(
            images=stack,
            output_dir=self.raw_path.preprocess_dir,
            params=get_default_params("caiman_cnmf_preprocessing"),
            nwbfile=self.nwb_input_config,
        )

    @stopwatch(callback=__stopwatch_callback)
    def generate_statdata(self) -> StatData:
        self.logger_.info("process 'generate_statdata' start.")

        expdb = ExpDbData(paths=[self.raw_path.tc_file, self.raw_path.ts_file])
        result = analyze_stats(
            expdb, self.raw_path.output_dir, get_default_params("analyze_stats")
        )
        stat = result.get("stat")
        assert isinstance(stat, StatData), "generate statdata failed"

        self.nwbfile[NWBDATASET.ORISTATS] = result["nwbfile"][NWBDATASET.ORISTATS]

        return stat

    @stopwatch(callback=__stopwatch_callback)
    def generate_cellmasks(self) -> int:
        self.logger_.info("process 'generate_cellmasks' start.")

        # Create directory for raw path only
        create_directory(self.raw_path.cellmask_dir)

        # csr_matrix to numpy array
        cellmask, imxx, ncells = self.load_raw_cellmask_data()

        fov = tifffile.imread(self.raw_path.fov_file).astype(np.double)
        fov_n = fov / np.max(fov)

        imx = imy = int(math.sqrt(imxx))

        cellmask = np.reshape(cellmask, (imx, imy, ncells), order="F")

        for i in range(ncells):
            cell_mask = np.where(cellmask[:, :, i] == 0, 0.0, 1.0)
            fov_highcontrast = np.minimum(fov_n / FOV_CONTRAST, 1)
            fov_cell_merge = np.repeat(fov_highcontrast[:, :, np.newaxis], 3, axis=2)
            fov_cell_merge[:, :, 1] = fov_cell_merge[:, :, 2] * (1 - cell_mask / 2)
            fov_cell_merge = np.round(fov_cell_merge * 255).astype(np.uint8)

            # Save image only for raw path
            save_image_with_thumb(
                join_filepath([self.raw_path.cellmask_dir, f"fov_cell_merge_{i}.png"]),
                fov_cell_merge,
            )

        # Verify generation was successful
        assert (
            len(
                glob(
                    join_filepath(
                        [self.raw_path.cellmask_dir, "fov_cell_merge_*.thumb.png"]
                    )
                )
            )
            == ncells
        ), f"generate cellmasks failed in {self.raw_path.cellmask_dir}"

        # Copy to pub path if different
        if self.raw_path.cellmask_dir != self.pub_path.cellmask_dir:
            create_directory(self.pub_path.cellmask_dir)
            self._copy_plots(self.raw_path.cellmask_dir, self.pub_path.cellmask_dir)

        return ncells

    @stopwatch(callback=__stopwatch_callback)
    def generate_plots(self, stat_data: StatData):
        self.logger_.info("process 'generate_plots' start.")

        is_circular = self.check_is_circular_data(self.exp_id)
        self.logger_.info(f"Data is {'circular' if is_circular else 'non-circular'}")

        dir_path = self.raw_path.plot_dir
        create_directory(dir_path)

        if is_circular:
            stat_data.tuning_curve.save_plot(dir_path)
            stat_data.tuning_curve_polar.save_plot(dir_path)

            stat_data.direction_responsivity_ratio.save_plot(dir_path)
            stat_data.orientation_responsivity_ratio.save_plot(dir_path)
            stat_data.direction_selectivity.save_plot(dir_path)
            stat_data.orientation_selectivity.save_plot(dir_path)
            stat_data.best_responsivity.save_plot(dir_path)

            stat_data.preferred_direction.save_plot(dir_path)
            stat_data.preferred_orientation.save_plot(dir_path)

            stat_data.direction_tuning_width.save_plot(dir_path)
            stat_data.orientation_tuning_width.save_plot(dir_path)
        else:
            stat_data.sf_tuning_curve.save_plot(dir_path)
            stat_data.stim_selectivity.save_plot(dir_path)
            stat_data.stim_responsivity.save_plot(dir_path)
            stat_data.sf_responsivity_ratio.save_plot(dir_path)

        # Copy all plots to pub path
        if self.raw_path.plot_dir != self.pub_path.plot_dir:
            create_directory(self.pub_path.plot_dir)
            self._copy_plots(self.raw_path.plot_dir, self.pub_path.plot_dir)

    @stopwatch(callback=__stopwatch_callback)
    def generate_pixelmaps(self):
        self.logger_.info("process 'generate_pixelmaps' start.")

        # Create directories
        create_directory(self.raw_path.pixelmap_dir)

        # Process only for raw path
        pixelmaps = glob(join_filepath([self.raw_path.orimaps_dir, "*_hc.tif"]))
        pixlemaps_with_num = glob(
            join_filepath([self.raw_path.orimaps_dir, "*_hc_*.tif"])
        )
        for pixelmap in [*pixelmaps, *pixlemaps_with_num]:
            img = tifffile.imread(pixelmap)
            file_name = os.path.splitext(os.path.basename(pixelmap))[0]
            save_image_with_thumb(
                join_filepath([self.raw_path.pixelmap_dir, f"{file_name}.png"]), img
            )

        # Verify generation was successful
        assert len(
            glob(join_filepath([self.raw_path.pixelmap_dir, "*.thumb.png"]))
        ) == len(pixelmaps) + len(
            pixlemaps_with_num
        ), f"generate pixelmaps failed in {self.raw_path.pixelmap_dir}"

        # Copy to pub path if different
        if self.raw_path.pixelmap_dir != self.pub_path.pixelmap_dir:
            create_directory(self.pub_path.pixelmap_dir)
            self._copy_plots(self.raw_path.pixelmap_dir, self.pub_path.pixelmap_dir)

    @stopwatch(callback=__stopwatch_callback)
    def generate_plots_spatial(self, stat_data: StatData):
        self.logger_.info("process 'generate_pca_analysis_plots' start.")

        timecourses = self.load_raw_timecourse_data()
        ncells = stat_data.ncells
        if timecourses.shape[0] != ncells:
            timecourses = timecourses.T

        roi_masks = self.process_roi_masks()

        dir_path = self.raw_path.plot_dir
        create_directory(dir_path)

        # Perform PCA analysis
        pca_results = pca_analysis(
            stat=stat_data,
            roi_masks=roi_masks,
            fluorescence=timecourses,
            output_dir=self.raw_path.output_dir,
            params=get_default_params("pca_analysis"),
            ts_file=self.raw_path.ts_file,
            nwbfile=self.nwbfile,
        )

        # Update nwbfile with PCA results
        self.nwbfile = pca_results["nwbfile"]

        # Save visualization objects with correct names
        stat_data.pca_analysis_variance.save_plot(dir_path)
        stat_data.pca_contribution.save_plot(dir_path)

        # Generate additional detailed visualization
        generate_pca_visualization(
            scores=stat_data.pca_scores,
            explained_variance=stat_data.pca_explained_variance,
            components=stat_data.pca_components,
            roi_masks=roi_masks,
            scores_ave=stat_data.pca_scores_ave,
            output_dir=dir_path,
        )

        self.logger_.info("process 'generate_kmeans_analysis_plots' start.")

        # Perform KMeans analysis
        kmeans_results = kmeans_analysis(
            stat=stat_data,
            roi_masks=roi_masks,
            fluorescence=timecourses,
            output_dir=self.raw_path.output_dir,
            params=get_default_params("kmeans_analysis"),
            ts_file=self.raw_path.ts_file,
            nwbfile=self.nwbfile,
        )

        # Update nwbfile with clustering results
        self.nwbfile = kmeans_results["nwbfile"]

        # Save visualization object
        stat_data.cluster_corr_matrix.save_plot(dir_path)

        # Generate additional visualizations
        generate_kmeans_visualization(
            all_labels=stat_data.all_labels,
            all_sorted_matrices=stat_data.all_sorted_matrices,
            fluorescence=stat_data.fluorescence,
            roi_masks=roi_masks,
            silhouette_scores=stat_data.silhouette_scores,
            optimal_clusters=stat_data.optimal_clusters,
            fluorescence_ave=stat_data.fluorescence_ave,
            output_dir=dir_path,
        )
        # Copy all plots to pub path
        if self.raw_path.plot_dir != self.pub_path.plot_dir:
            self._copy_plots(self.raw_path.plot_dir, self.pub_path.plot_dir)

    @stopwatch(callback=__stopwatch_callback)
    def load_exp_metadata(self) -> Tuple[dict, dict]:
        if not os.path.exists(self.raw_path.exp_metadata_file):
            return (None, None)
        else:
            with open(self.raw_path.exp_metadata_file) as f:
                attributes = json.load(f)
                view_attributes = extract_experiment_view_attributes(attributes)

                if not view_attributes:
                    raise KeyError("Invalid metadata format")

        return (attributes, view_attributes)

    @stopwatch(callback=__stopwatch_callback)
    def save_nwb(self, metadata: dict):
        if self.raw_path.microscope_file is not None:
            self.nwb_input_config[NWBDATASET.IMAGE_SERIES][
                "external_file"
            ] = self.raw_path.microscope_file
        self.nwb_input_config[NWBDATASET.LAB_METADATA] = metadata

        # Save NWB file to raw path only
        save_nwb(self.raw_path.nwb_file, self.nwb_input_config, self.nwbfile)

        # Copy to public path if different
        nwb_public = self.pub_path.nwb_file
        if self.raw_path.nwb_file != self.pub_path.nwb_file:
            self.logger_.info(
                f"Copying NWB file from {self.raw_path.nwb_file} to {nwb_public}"
            )
            # Make sure the destination directory exists
            create_directory(os.path.dirname(self.pub_path.nwb_file))
            shutil.copy2(self.raw_path.nwb_file, self.pub_path.nwb_file)

    def _copy_plots(self, source_dir, dest_dir):
        """Copy all PNG files from source directory to destination directory."""

        self.logger_.info(f"Copying plots from {source_dir} to {dest_dir}")

        # Copy both regular PNGs and thumbnails
        for pattern in ["*.png", "*.thumb.png"]:
            for file_path in glob(join_filepath([source_dir, pattern])):
                dest_path = join_filepath([dest_dir, os.path.basename(file_path)])
                shutil.copy2(file_path, dest_path)

    def _configure_matplotlib(self):
        """Configure matplotlib for better performance."""
        import matplotlib

        matplotlib.use("Agg")  # Use non-interactive backend
        import matplotlib.pyplot as plt

        # Disable interactive mode
        plt.ioff()
        plt.style.use("fast")

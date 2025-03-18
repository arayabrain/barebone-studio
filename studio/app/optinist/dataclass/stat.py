import numpy as np

from studio.app.common.dataclass.bar import BarData
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.heatmap import HeatMapData
from studio.app.common.dataclass.histogram import HistogramData
from studio.app.common.dataclass.line import LineData
from studio.app.common.dataclass.pie import PieData
from studio.app.common.dataclass.polar import PolarData
from studio.app.common.dataclass.scatter import ScatterData
from studio.app.optinist.core.nwb.oristat import (
    ANOVA_PROPS,
    ANOVA_TYPES,
    CURVEFIT_PROPS,
    CURVEFIT_TYPES,
    FILE_CONVERT_PROPS,
    FILE_CONVERT_TYPES,
    PARAM_TYPES,
    VECTOR_AVERAGE_PROPS,
    VECTOR_AVERAGE_TYPES,
)


class StatData(BaseData):
    def __init__(self, data_table=np.empty((1, 1, 1)), file_name="stat"):
        super().__init__(file_name)
        # params
        self.ncells, self.ntrials, self.nstimplus = data_table.shape
        self.data_table = data_table
        self.nstim = self.nstimplus - 1
        half_nstim = int(self.nstim / 2)
        self.p_value_threshold = 0.05
        self.r_best_threshold = 0.05
        self.si_threshold = 0.3

        # --- stat_file_convert ---
        self.nstim_per_trial = None
        self.dir_ratio_change = np.full((self.ncells, self.nstim), np.NaN)
        self.best_dir = np.full(self.ncells, np.NaN)
        self.null_dir = np.full(self.ncells, np.NaN)
        self.r_best_dir = np.full(self.ncells, np.NaN)
        self.r_null_dir = np.full(self.ncells, np.NaN)
        self.r_min_dir = np.full(self.ncells, np.NaN)
        self.di = np.full(self.ncells, np.NaN)
        self.dsi = None
        self.ori_ratio_change = np.full((self.ncells, half_nstim), np.NaN)
        self.best_ori = np.full(self.ncells, np.NaN)
        self.null_ori = np.full(self.ncells, np.NaN)
        self.r_best_ori = np.full(self.ncells, np.NaN)
        self.r_null_ori = np.full(self.ncells, np.NaN)
        self.r_min_ori = np.full(self.ncells, np.NaN)
        self.oi = np.full(self.ncells, np.NaN)
        self.osi = None
        self.best_sf = np.full(self.ncells, np.NaN)
        self.min_sf = np.full(self.ncells, np.NaN)
        self.r_best_sf = np.full(self.ncells, np.NaN)
        self.r_min_sf = np.full(self.ncells, np.NaN)
        self.si = np.full(self.ncells, np.NaN)
        self.sf_si = np.full(self.ncells, np.NaN)
        self.sf_si = np.full(self.ncells, np.NaN)
        self.sf_bandwidth = np.full(self.ncells, np.NaN)
        self.index_sf_responsive_cell = None
        self.ncells_sf_responsive_cell = None
        self.index_sf_selective_cell = None
        self.ncells_sf_selective_cell = None

        # --- anova1_mult ---
        self.p_value_resp = np.full(self.ncells, np.NaN)
        self.sig_epochs_resp = np.full(
            (self.ncells, self.nstimplus, self.nstimplus), np.NaN
        )
        self.p_value_sel = np.full(self.ncells, np.NaN)
        self.sig_epochs_sel = np.full((self.ncells, self.nstim, self.nstim), np.NaN)
        self.dir_sig = np.full(self.ncells, np.NaN)
        self.p_value_ori_resp = np.full(self.ncells, np.NaN)
        self.sig_epochs_ori_resp = np.full(
            (self.ncells, half_nstim + 1, half_nstim + 1), np.NaN
        )
        self.p_value_ori_sel = np.full(self.ncells, np.NaN)
        self.sig_epochs_ori_sel = np.full((self.ncells, half_nstim, half_nstim), np.NaN)
        self.index_visually_responsive_cell = None
        self.ncells_visually_responsive_cell = None
        self.index_direction_selective_cell = None
        self.ncells_direction_selective_cell = None
        self.index_orientation_selective_cell = None
        self.ncells_orientation_selective_cell = None

        # --- vector_average ---
        self.dir_vector_angle = np.full(self.ncells, np.NaN)
        self.dir_vector_mag = np.full(self.ncells, np.NaN)
        self.dir_vector_tune = np.full(self.ncells, np.NaN)
        self.ori_vector_angle = np.full(self.ncells, np.NaN)
        self.ori_vector_mag = np.full(self.ncells, np.NaN)
        self.ori_vector_tune = np.full(self.ncells, np.NaN)

        # --- curvefit_tuning ---
        self.best_dir_interp = np.full(self.ncells, np.NaN)
        self.null_dir_interp = np.full(self.ncells, np.NaN)
        self.r_best_dir_interp = np.full(self.ncells, np.NaN)
        self.r_null_dir_interp = np.full(self.ncells, np.NaN)
        self.di_interp = np.full(self.ncells, np.NaN)
        self.best_dir_fit = np.full(self.ncells, np.NaN)
        self.null_dir_fit = np.full(self.ncells, np.NaN)
        self.r_best_dir_fit = np.full(self.ncells, np.NaN)
        self.r_null_dir_fit = np.full(self.ncells, np.NaN)
        self.di_fit = np.full(self.ncells, np.NaN)
        self.ds = np.full(self.ncells, np.NaN)
        self.dir_tuning_width = np.full(self.ncells, np.NaN)
        self.dir_a1 = np.full(self.ncells, np.NaN)
        self.dir_a2 = np.full(self.ncells, np.NaN)
        self.dir_k1 = np.full(self.ncells, np.NaN)
        self.dir_k2 = np.full(self.ncells, np.NaN)
        self.best_ori_fit = np.full(self.ncells, np.NaN)
        self.ori_tuning_width = np.full(self.ncells, np.NaN)
        self.ori_k1 = np.full(self.ncells, np.NaN)
        self.ori_a1 = np.full(self.ncells, np.NaN)

        # --- PCA ---
        self.pca_scores = np.full((self.ncells, self.ncells), np.NaN)
        self.pca_explained_variance = np.full(self.ncells, np.NaN)
        self.pca_components = None
        self.pca_scores_ave = None

        # --- kmeans ---
        self.cluster_labels = np.full(self.ncells, np.NaN)
        self.cluster_corr_matrix = np.full((self.ncells, self.ncells), np.NaN)

    # --- stat_file_convert ---
    def set_file_convert_props(self, sf_params=None):
        """Set up standard tuning curve and spatial frequency properties"""
        # Original direction/orientation calculations
        self.dsi = (self.r_best_dir - np.maximum(self.r_null_dir, 0)) / (
            self.r_best_dir + np.maximum(self.r_null_dir, 0)
        )
        self.osi = (self.r_best_ori - np.maximum(self.r_null_ori, 0)) / (
            self.r_best_ori + np.maximum(self.r_null_ori, 0)
        )
        self.tuning_curve = LineData(
            data=self.dir_ratio_change,
            columns=np.arange(0, 360, 360 / self.nstim_per_trial),
            file_name="tuning_curve",
        )
        self.tuning_curve_polar = PolarData(
            data=self.dir_ratio_change,
            thetas=np.linspace(
                0, 360, self.dir_ratio_change[0].shape[0], endpoint=False
            ),
            file_name="tuning_curve_polar",
        )

        # Spatial frequency responsive and selective cells
        self.index_sf_responsive_cell = np.where(
            (self.r_best_sf >= self.r_best_threshold) & (~np.isnan(self.r_best_sf)),
            True,
            False,
        )
        self.ncells_sf_responsive_cell = np.sum(self.index_sf_responsive_cell)

        self.index_sf_selective_cell = np.where(
            self.index_sf_responsive_cell & (self.sf_si >= self.si_threshold),
            True,
            False,
        )
        self.ncells_sf_selective_cell = np.sum(self.index_sf_selective_cell)

        # Create spatial frequency visualization data structures
        self.stim_selectivity = HistogramData(
            data=self.sf_si[self.index_sf_responsive_cell]
            if np.any(self.index_sf_responsive_cell)
            else np.array([0]),
            file_name="sf_selectivity",
        )

        self.stim_responsivity = HistogramData(
            data=self.r_best_sf[self.index_sf_responsive_cell] * 100
            if np.any(self.index_sf_responsive_cell)
            else np.array([0]),
            file_name="sf_responsivity",
        )

        self.sf_responsivity_ratio = PieData(
            data=np.array(
                (
                    self.ncells_sf_selective_cell,
                    self.ncells_sf_responsive_cell - self.ncells_sf_selective_cell,
                    self.ncells - self.ncells_sf_responsive_cell,
                ),
                dtype=np.float64,
            ),
            labels=["SF Selective", "SF Responsive", "Non-responsive"],
            file_name="sf_responsivity_ratio",
        )

        # Use spatial frequency parameters for scaling if provided
        sf_min = 0
        sf_max = 1
        if sf_params:
            sf_min = sf_params.get("sf_min_value", 0)
            sf_max = sf_params.get("sf_max_value", 1)

        # Create spatial frequency tuning curve with appropriate scaling
        num_sf_points = self.dir_ratio_change.shape[1]
        self.sf_tuning_curve = LineData(
            data=self.dir_ratio_change,
            columns=np.linspace(sf_min, sf_max, num_sf_points),
            file_name="spatial_frequency_tuning",
        )

    # --- anova ---
    def set_anova_props(self):
        self.index_visually_responsive_cell = np.where(
            (self.p_value_resp < self.p_value_threshold)
            & (self.r_best_dir >= self.r_best_threshold),
            True,
            False,
        )

        self.ncells_visually_responsive_cell = np.sum(
            self.index_visually_responsive_cell
        )

        self.index_direction_selective_cell = np.where(
            self.index_visually_responsive_cell & (self.dsi >= self.si_threshold),
            True,
            False,
        )
        self.ncells_direction_selective_cell = np.sum(
            self.index_direction_selective_cell
        )

        self.index_orientation_selective_cell = np.where(
            self.index_visually_responsive_cell & (self.osi >= self.si_threshold),
            True,
            False,
        )
        self.ncells_orientation_selective_cell = np.sum(
            self.index_orientation_selective_cell
        )

        self.direction_responsivity_ratio = PieData(
            data=np.array(
                (
                    self.ncells_direction_selective_cell,
                    self.ncells_visually_responsive_cell
                    - self.ncells_direction_selective_cell,
                    self.ncells - self.ncells_visually_responsive_cell,
                )
            ),
            labels=["DS", "non-DS", "non-responsive"],
            file_name="direction_responsivity_ratio",
        )

        self.orientation_responsivity_ratio = PieData(
            data=np.array(
                (
                    self.ncells_orientation_selective_cell,
                    self.ncells_visually_responsive_cell
                    - self.ncells_orientation_selective_cell,
                    self.ncells - self.ncells_visually_responsive_cell,
                )
            ),
            labels=["OS", "non-OS", "non-responsive"],
            file_name="orientation_responsivity_ratio",
        )

        self.direction_selectivity = HistogramData(
            data=self.dsi[self.index_direction_selective_cell],
            file_name="direction_selectivity",
        )

        self.orientation_selectivity = HistogramData(
            data=self.osi[self.index_orientation_selective_cell],
            file_name="orientation_selectivity",
        )

        self.best_responsivity = HistogramData(
            data=self.r_best_dir[self.index_visually_responsive_cell] * 100,
            file_name="best_responsivity",
        )

    # --- vector_average ---
    def set_vector_average_props(self):
        self.preferred_direction = HistogramData(
            data=self.dir_vector_angle[self.index_direction_selective_cell],
            file_name="preferred_direction",
        )

        self.preferred_orientation = HistogramData(
            data=self.ori_vector_angle[self.index_orientation_selective_cell],
            file_name="preferred_orientation",
        )

    # --- curvefit_tuning ---
    def set_curvefit_props(self):
        self.direction_tuning_width = HistogramData(
            data=self.dir_tuning_width[self.index_direction_selective_cell],
            file_name="direction_tuning_width",
        )

        self.orientation_tuning_width = HistogramData(
            data=self.ori_tuning_width[self.index_orientation_selective_cell],
            file_name="orientation_tuning_width",
        )

    # --- pca ---
    def set_pca_props(self):
        """Create visualization data structures for PCA results"""
        self.pca_analysis_variance = BarData(
            data=self.pca_explained_variance[
                : min(10, len(self.pca_explained_variance))
            ],
            file_name="pca_analysis_variance",
        )

        self.pca_contribution = BarData(
            data=self.pca_components[: min(5, self.pca_components.shape[0])],
            index=[f"PC {i+1}" for i in range(min(5, self.pca_components.shape[0]))],
            file_name="pca_contribution_001",
        )

    # --- kmeans ---
    def set_kmeans_props(self):
        """Set references to visualization files"""
        self.cluster_corr_matrix = HeatMapData(
            data=np.zeros((1, 1)), columns=[0], file_name="clustering_analysis_001"
        )

        # ScatterData does NOT accept columns
        self.cluster_silhouette_scores = ScatterData(
            data=np.zeros((2, 1)), file_name="cluster_silhouette_scores"
        )

        # HeatMapData accepts columns
        self.cluster_spatial_map = HeatMapData(
            data=np.zeros((1, 1)), columns=[0], file_name="cluster_spatial_map_001"
        )

        # LineData requires columns
        self.cluster_time_courses = LineData(
            data=np.zeros(1), columns=[0], file_name="cluster_time_course_001"
        )

    @property
    def nwb_dict_file_convert(self) -> dict:
        nwb_dict = {
            key: self.__dict__[key]
            for key in [*PARAM_TYPES.keys(), *FILE_CONVERT_TYPES.keys()]
        }

        for k in FILE_CONVERT_PROPS.keys():
            nwb_dict[k] = self.__dict__[k].data

        return nwb_dict

    @property
    def nwb_dict_anova(self) -> dict:
        nwb_dict = {key: self.__dict__[key] for key in list(ANOVA_TYPES.keys())}

        for k in ANOVA_PROPS.keys():
            nwb_dict[k] = self.__dict__[k].data

        return nwb_dict

    @property
    def nwb_dict_vector_average(self) -> dict:
        nwb_dict = {
            key: self.__dict__[key] for key in list(VECTOR_AVERAGE_TYPES.keys())
        }

        for k in VECTOR_AVERAGE_PROPS.keys():
            nwb_dict[k] = self.__dict__[k].data

        return nwb_dict

    @property
    def nwb_dict_curvefit(self) -> dict:
        nwb_dict = {key: self.__dict__[key] for key in list(CURVEFIT_TYPES.keys())}

        for k in CURVEFIT_PROPS.keys():
            nwb_dict[k] = self.__dict__[k].data

        return nwb_dict

    @property
    def nwb_dict_pca(self) -> dict:
        nwb_dict = {}

        # Only include fields that are defined in PCA_TYPES
        if hasattr(self, "pca_scores") and self.pca_scores is not None:
            nwb_dict["pca_scores"] = self.pca_scores
        if (
            hasattr(self, "pca_explained_variance")
            and self.pca_explained_variance is not None
        ):
            nwb_dict["pca_explained_variance"] = self.pca_explained_variance
        if hasattr(self, "pca_components") and self.pca_components is not None:
            nwb_dict["pca_components"] = self.pca_components

        return nwb_dict

    @property
    def nwb_dict_kmeans(self) -> dict:
        nwb_dict = {}

        # Only include fields that are defined in KMEANS_TYPES
        if hasattr(self, "cluster_labels") and self.cluster_labels is not None:
            nwb_dict["cluster_labels"] = self.cluster_labels
        if (
            hasattr(self, "cluster_corr_matrix")
            and self.cluster_corr_matrix is not None
        ):
            nwb_dict["cluster_corr_matrix"] = self.cluster_corr_matrix

        return nwb_dict

    @property
    def nwb_dict_all(self) -> dict:
        return {
            **self.nwb_dict_file_convert,
            **self.nwb_dict_anova,
            **self.nwb_dict_vector_average,
            **self.nwb_dict_curvefit,
            **self.nwb_dict_pca,
            **self.nwb_dict_kmeans,
        }

    @classmethod
    def fill_nan_with_none(cls, data):
        return np.where(np.isnan(data), None, data)

from pynwb import get_class, load_namespaces
from pynwb.spec import NWBDatasetSpec, NWBGroupSpec, NWBNamespaceBuilder

name = "oristats"
ns_path = f"{name}.namespace.yaml"
ext_source = f"{name}.extensions.yaml"

PARAM_TYPES = {
    "ncells": "int",
    "ntrials": "int",
    "nstimplus": "int",
    "data_table": (
        "float",
        [(None, None), (None, None, None), (None, None, None, None)],
    ),
    "nstim": "int",
    "p_value_threshold": "float",
    "r_best_threshold": "float",
    "si_threshold": "float",
}

FILE_CONVERT_TYPES = {
    "nstim_per_trial": "int",
    "dir_ratio_change": ("float", (None, None)),
    "best_dir": ("float", (None,)),
    "null_dir": ("float", (None,)),
    "r_best_dir": ("float", (None,)),
    "r_null_dir": ("float", (None,)),
    "r_min_dir": ("float", (None,)),
    "di": ("float", (None,)),
    "dsi": ("float", (None,)),
    "ori_ratio_change": ("float", (None, None)),
    "best_ori": ("float", (None,)),
    "null_ori": ("float", (None,)),
    "r_best_ori": ("float", (None,)),
    "r_null_ori": ("float", (None,)),
    "r_min_ori": ("float", (None,)),
    "oi": ("float", (None,)),
    "osi": ("float", (None,)),
}

FILE_CONVERT_PROPS = {
    "tuning_curve": ("float", (None, None)),
    "tuning_curve_polar": ("float", (None, None)),
    "stim_selectivity": ("float", (None, None)),
    "stim_responsivity": ("float", (None, None)),
    "sf_responsivity_ratio": ("float", (None, None)),
}

ANOVA_TYPES = {
    "p_value_resp": ("float", (None,)),
    "sig_epochs_resp": ("float", (None, None, None)),
    "p_value_sel": ("float", (None,)),
    "sig_epochs_sel": ("float", (None, None, None)),
    "dir_sig": ("float", (None,)),
    "p_value_ori_resp": ("float", (None,)),
    "sig_epochs_ori_resp": ("float", (None, None, None)),
    "p_value_ori_sel": ("float", (None,)),
    "sig_epochs_ori_sel": ("float", (None, None, None)),
    "index_visually_responsive_cell": ("bool", (None,)),
    "ncells_visually_responsive_cell": "int",
    "index_direction_selective_cell": ("bool", (None,)),
    "ncells_direction_selective_cell": "int",
    "index_orientation_selective_cell": ("bool", (None,)),
    "ncells_orientation_selective_cell": "int",
}

ANOVA_PROPS = {
    "direction_responsivity_ratio": ("float", (None, None)),
    "orientation_responsivity_ratio": ("float", (None, None)),
    "direction_selectivity": ("float", (None, None)),
    "orientation_selectivity": ("float", (None, None)),
    "best_responsivity": ("float", (None, None)),
}

VECTOR_AVERAGE_TYPES = {
    "dir_vector_angle": ("float", (None,)),
    "dir_vector_mag": ("float", (None,)),
    "dir_vector_tune": ("float", (None,)),
    "ori_vector_angle": ("float", (None,)),
    "ori_vector_mag": ("float", (None,)),
    "ori_vector_tune": ("float", (None,)),
}

VECTOR_AVERAGE_PROPS = {
    "preferred_direction": ("float", (None, None)),
    "preferred_orientation": ("float", (None, None)),
}

CURVEFIT_TYPES = {
    "best_dir_interp": ("float", (None,)),
    "null_dir_interp": ("float", (None,)),
    "r_best_dir_interp": ("float", (None,)),
    "r_null_dir_interp": ("float", (None,)),
    "di_interp": ("float", (None,)),
    "best_dir_fit": ("float", (None,)),
    "null_dir_fit": ("float", (None,)),
    "r_best_dir_fit": ("float", (None,)),
    "r_null_dir_fit": ("float", (None,)),
    "di_fit": ("float", (None,)),
    "ds": ("float", (None,)),
    "dir_tuning_width": ("float", (None,)),
    "dir_a1": ("float", (None,)),
    "dir_a2": ("float", (None,)),
    "dir_k1": ("float", (None,)),
    "dir_k2": ("float", (None,)),
    "best_ori_fit": ("float", (None,)),
    "ori_tuning_width": ("float", (None,)),
    "ori_a1": ("float", (None,)),
    "ori_k1": ("float", (None,)),
}

CURVEFIT_PROPS = {
    "direction_tuning_width": ("float", (None, None)),
    "orientation_tuning_width": ("float", (None, None)),
}

PCA_TYPES = {
    "pca_scores": ("float", (None, None)),
    "pca_explained_variance": ("float", (None,)),
    "pca_components": ("float", (None, None)),
    "pca_scores_ave": ("float", (None, None)),
}

KMEANS_TYPES = {
    "cluster_labels": ("int", (None,)),
    "cluster_corr_matrix": ("float", (None, None)),
    "silhouette_scores": ("float", (None,)),
    "optimal_clusters": "int",
}


def get_dataset_list(types: dict) -> list:
    return [
        (
            NWBDatasetSpec(doc=k, name=k, dtype=v[0], shape=v[1], quantity="?")
            if isinstance(v, tuple)
            else NWBDatasetSpec(doc=k, name=k, dtype=v, quantity="?")
        )
        for k, v in types.items()
    ]


oristat_ext = NWBGroupSpec(
    doc="oristats",
    datasets=[
        *get_dataset_list(PARAM_TYPES),
        *get_dataset_list(FILE_CONVERT_TYPES),
        *get_dataset_list(FILE_CONVERT_PROPS),
        *get_dataset_list(ANOVA_TYPES),
        *get_dataset_list(ANOVA_PROPS),
        *get_dataset_list(VECTOR_AVERAGE_TYPES),
        *get_dataset_list(VECTOR_AVERAGE_PROPS),
        *get_dataset_list(CURVEFIT_TYPES),
        *get_dataset_list(CURVEFIT_PROPS),
        *get_dataset_list(PCA_TYPES),
        *get_dataset_list(KMEANS_TYPES),
    ],
    name="oristats",
    neurodata_type_def="Oristats",
    neurodata_type_inc="NWBContainer",
)

ns_builder = NWBNamespaceBuilder(f"{name} extensions", name, version="0.1.0")
ns_builder.add_spec(ext_source, oristat_ext)
ns_builder.export(ns_path)
load_namespaces(ns_path)

Oristats = get_class("Oristats", name)

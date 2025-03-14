import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import PCA

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.dataclass.utils import save_thumbnail
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass.stat import StatData

logger = AppLogger.get_logger()


def pca_analysis(
    stat: StatData, cnmf_info: dict, output_dir: str, params: dict = None, **kwargs
) -> dict:
    """Perform PCA analysis on CNMF results"""

    # Get the fluorescence data
    fluorescence = cnmf_info["fluorescence"].data

    # If iscell data is available, use it to filter fluorescence
    if "iscell" in cnmf_info and cnmf_info["iscell"] is not None:
        iscell = cnmf_info["iscell"].data
        if len(iscell) == fluorescence.shape[0]:
            good_indices = np.where(iscell == 1)[0]
            logger.info(f"Using iscell {len(iscell)} total cells for PCA")

            if len(good_indices) > 0:
                # Filter fluorescence to only include good components
                fluorescence = fluorescence[good_indices]
                # logger.info(f"Filtered fluorescence shape: {fluorescence.shape}")

    n_cells = fluorescence.shape[0]
    logger.info(f"PCA will use {n_cells} cells")

    # Check if we have enough ROIs for PCA
    if n_cells < 2:
        # Handle the case of insufficient ROIs for PCA
        # Create dummy placeholders to avoid errors in set_pca_props
        dummy_scores = np.zeros((1, 1))
        dummy_components = np.zeros((1, 1))
        dummy_explained_variance = np.zeros(1)

        stat.pca_scores = dummy_scores
        stat.pca_components = dummy_components
        stat.pca_explained_variance = dummy_explained_variance

        # Store ROI masks for visualization
        stat.roi_masks = cnmf_info["cell_roi"].data

        # Still create visualization objects for proper UI display
        stat.set_pca_props()

        # Add message to nwbfile
        nwbfile = kwargs.get("nwbfile", {})
        pca_dict = {
            "pca_scores": dummy_scores,
            "pca_components": dummy_components,
            "pca_explained_variance": dummy_explained_variance,
        }
        nwbfile = {
            NWBDATASET.ORISTATS: {**nwbfile.get(NWBDATASET.ORISTATS, {}), **pca_dict}
        }

        return {
            "stat": stat,
            "pca_analysis": stat.pca_analysis,
            "pca_analysis_variance": stat.pca_analysis_variance,
            "pca_contribution": stat.pca_contribution,
            "nwbfile": nwbfile,
        }

    # Set default parameters if none provided
    if params is None:
        params = {"n_components": min(50, n_cells), "standard_norm": True}
    else:
        # Extract parameters from the nested structure if present
        pca_params = params.get("PCA", {})
        params = {
            "n_components": min(pca_params.get("n_components", 50), n_cells),
            "standard_norm": params.get("standard_mean", True),
        }

    # Prepare data
    if params.get("standard_norm", True):
        # Center the data
        data = fluorescence - np.mean(fluorescence, axis=1, keepdims=True)
        # Scale to unit variance
        std_values = np.std(data, axis=1, keepdims=True)
        # Avoid division by zero
        std_values[std_values == 0] = 1.0
        data = data / std_values
    else:
        data = fluorescence

    # Perform PCA
    pca = PCA(n_components=params["n_components"])
    scores = pca.fit_transform(data.T)  # time x components
    components = pca.components_  # components x cells
    explained_variance = pca.explained_variance_ratio_ * 100

    # Store results in StatData
    stat.pca_scores = scores
    stat.pca_components = components
    stat.pca_explained_variance = explained_variance

    # Store ROI masks for visualization
    stat.roi_masks = cnmf_info["cell_roi"].data

    # Create visualization objects within the function
    stat.set_pca_props()

    # Add to nwbfile if needed
    nwbfile = kwargs.get("nwbfile", {})
    pca_dict = {
        "pca_scores": scores,
        "pca_components": components,
        "pca_explained_variance": explained_variance,
    }
    nwbfile = {
        NWBDATASET.ORISTATS: {**nwbfile.get(NWBDATASET.ORISTATS, {}), **pca_dict}
    }

    return {
        "stat": stat,
        "pca_analysis": stat.pca_analysis,
        "pca_analysis_variance": stat.pca_analysis_variance,
        "pca_contribution": stat.pca_contribution,
        "nwbfile": nwbfile,
    }


def generate_pca_visualization(
    scores,
    explained_variance,
    components,
    roi_masks,
    output_dir,
):
    """
    Generate PCA visualization with separate files for each component

    Parameters
    ----------
    scores : ndarray
        PCA scores matrix (time x components)
    explained_variance : ndarray
        Explained variance percentages
    components : ndarray
        PCA components matrix (components x cells)
    roi_masks : ndarray
        2D ROI mask where each non-NaN value identifies a cell
    output_dir : str
        Directory for saving output files
    """
    # Check if inputs are valid
    if components is None or scores is None:
        logger.warning("Warning: Missing PCA components or scores")
        return

    if roi_masks is not None and hasattr(roi_masks, "shape"):
        # Confirm number of unique ROI IDs (excluding NaN)
        non_nan_mask = ~np.isnan(roi_masks)
        if np.any(non_nan_mask):
            unique_ids = np.unique(roi_masks[non_nan_mask])
            for val in unique_ids:
                count = np.sum(np.isclose(roi_masks, val))
                logger.info(f"  ROI ID {val}: {count} pixels")
        else:
            logger.warning("WARNING: All values in ROI mask are NaN")

    # Handle the case of insufficient ROIs - create error images
    is_data_insufficient = (
        components.shape[0] < 2
        or scores.shape[1] < 2  # Less than 2 components
        or np.allclose(components, 0, atol=1e-7)  # Less than 2 score dimensions
        or np.allclose(scores, 0, atol=1e-7)  # All component values near zero
        or np.all(np.isnan(components))  # All score values near zero
        or np.all(np.isnan(scores))  # All NaN values  # All NaN values
    )

    if is_data_insufficient:
        # Create error image for variance plot
        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for PCA analysis.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        variance_path = join_filepath([output_dir, "pca_analysis_variance.png"])
        plt.savefig(variance_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(variance_path)

        # Create error image for scatter plot
        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for PCA analysis.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        scatter_path = join_filepath([output_dir, "pca_analysis.png"])
        plt.savefig(scatter_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(scatter_path)

        # Create error image for contribution plot
        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for PCA analysis.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        contrib_path = join_filepath([output_dir, "pca_contribution.png"])
        plt.savefig(contrib_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(contrib_path)

        # Error image for spatial components
        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for PCA analysis.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        spatial_path = join_filepath([output_dir, "pca_component_1_spatial.png"])
        plt.savefig(spatial_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(spatial_path)

        # Error image for time components
        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for PCA analysis.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        time_path = join_filepath([output_dir, "pca_component_1_time.png"])
        plt.savefig(time_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(time_path)

        return

    # Number of components to visualize
    num_components = min(50, components.shape[0], scores.shape[1])

    # Set to 10 as too many make legend illegible
    plots_to_show = 10

    # 1. Plot explained variance
    plt.figure()
    num_display = min(plots_to_show, len(explained_variance))
    plt.bar(range(1, num_display + 1), explained_variance[:num_display])
    plt.title("Explained Variance")
    plt.xlabel("Principal Component")
    plt.ylabel("Explained Variance (%)")
    plt.grid(True, alpha=0.3)

    variance_path = join_filepath([output_dir, "pca_analysis_variance.png"])
    plt.savefig(variance_path, bbox_inches="tight")
    plt.close()
    save_thumbnail(variance_path)

    # 2. Create PCA scatter plot (first 2-3 components)
    plt.figure()
    if scores.shape[1] >= 2:
        plt.scatter(scores[:, 0], scores[:, 1], alpha=0.7)
        plt.xlabel("PC 1")
        plt.ylabel("PC 2")

        if scores.shape[1] >= 3:
            plt.figure()
            plt.scatter(
                scores[:, 0], scores[:, 1], c=scores[:, 2], cmap="viridis", alpha=0.7
            )
            plt.colorbar(label="PC 3")
            plt.xlabel("PC 1")
            plt.ylabel("PC 2")

    scatter_path = join_filepath([output_dir, "pca_analysis.png"])
    plt.savefig(scatter_path, bbox_inches="tight")
    plt.close()
    save_thumbnail(scatter_path)

    # 3. For each component, create time course and spatial map
    for i in range(num_components):
        plt.figure()
        plt.plot(scores[:, i], linewidth=2)
        plt.title(f"PC {i+1} Time Course")
        plt.xlabel("Time")
        plt.ylabel("Component Value")
        plt.grid(True, alpha=0.3)

        time_path = join_filepath([output_dir, f"pca_component_{i+1}_time.png"])
        plt.savefig(time_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(time_path)

        # 4. Spatial map - attempt only if roi_masks has appropriate shape
        component_weights = components[i]  # Using actual weights, not absolute values

        # Create spatial component maps
        if roi_masks is not None and hasattr(roi_masks, "shape"):
            try:
                # Extract valid cell IDs (non-NaN values) from roi_masks
                non_nan_mask = (
                    ~np.isnan(roi_masks)
                    if np.any(np.isnan(roi_masks))
                    else np.ones_like(roi_masks, dtype=bool)
                )

                if np.any(non_nan_mask):
                    # Create component map
                    component_map = np.full_like(roi_masks, np.nan)

                    # Get unique cell IDs
                    valid_ids = np.unique(roi_masks[non_nan_mask])
                    valid_ids = np.sort(valid_ids)

                    # Map each cell's weight to its spatial location
                    for idx, cell_id in enumerate(valid_ids):
                        if idx < len(component_weights):
                            # Find pixels for this cell and assign component weight
                            cell_mask = np.isclose(roi_masks, cell_id)
                            if np.any(cell_mask):
                                component_map[cell_mask] = component_weights[idx]

                    # Check if map has valid data
                    if not np.all(np.isnan(component_map)):
                        # Use symmetric divergent colormap with consistent scaling
                        vmax = np.nanmax(np.abs(component_map))

                        plt.figure()
                        im = plt.imshow(
                            component_map, cmap="RdBu_r", vmin=-vmax, vmax=vmax
                        )
                        plt.colorbar(im, label="Component Weight")
                        plt.title(f"PC {i+1} Spatial Map")

                        spatial_path = join_filepath(
                            [output_dir, f"pca_component_{i+1}_spatial.png"]
                        )
                        plt.savefig(spatial_path, bbox_inches="tight")
                        plt.close()
                        save_thumbnail(spatial_path)
                    else:
                        raise ValueError("No valid values in component map")
                else:
                    raise ValueError("No non-NaN values found in ROI mask")

            except Exception as e:
                logger.error(f"Error creating spatial map for PC {i+1}: {str(e)}")

                # Create fallback visualization
                plt.figure()
                plt.bar(range(len(component_weights)), component_weights)
                plt.title(f"PC {i+1} Component Weights")
                plt.xlabel("Cell Index")
                plt.ylabel("Weight")
                plt.grid(True, alpha=0.3)

                spatial_path = join_filepath(
                    [output_dir, f"pca_component_{i+1}_spatial.png"]
                )
                plt.savefig(spatial_path, bbox_inches="tight")
                plt.close()
                save_thumbnail(spatial_path)

                logger.warning(f"Created fallback bar visualization for PC {i+1}")
        else:
            # Create alternative visualization using direct component values
            plt.figure()
            plt.bar(range(len(component_weights)), component_weights)
            plt.title(f"PC {i+1} Component Weights")
            plt.xlabel("Cell Index")
            plt.ylabel("Weight")
            plt.grid(True, alpha=0.3)

            spatial_path = join_filepath(
                [output_dir, f"pca_component_{i+1}_spatial.png"]
            )
            plt.savefig(spatial_path, bbox_inches="tight")
            plt.close()
            save_thumbnail(spatial_path)

    # 5. Save the contribution weights as a separate visualization
    plt.figure()
    top_n = min(plots_to_show, components.shape[0])
    for i in range(top_n):
        plt.bar(
            range(len(components[i])),
            components[i],  # Using actual weights, not absolute values
            alpha=0.7,
            label=f"PC {i+1}",
        )
    plt.xlabel("Cell Index")
    plt.ylabel("Component Weight")
    plt.title("PCA Component Contributions")
    plt.legend()
    plt.grid(True, alpha=0.3)

    contrib_path = join_filepath([output_dir, "pca_contribution.png"])
    plt.savefig(contrib_path, bbox_inches="tight")
    plt.close()
    save_thumbnail(contrib_path)

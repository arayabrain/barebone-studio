import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import PCA

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.dataclass.utils import save_thumbnail
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass import ExpDbData
from studio.app.optinist.dataclass.stat import StatData

logger = AppLogger.get_logger()


def pca_analysis(
    stat: StatData,
    roi_masks: np.ndarray,
    fluorescence: np.ndarray,
    output_dir: str,
    params: dict = None,
    ts_file=None,
    **kwargs,
) -> dict:
    """
    Perform PCA analysis on CNMF results with trial structure support

    Parameters
    ----------
    stat : StatData
        StatData object to store analysis results
    roi_masks data: np.ndarray
    fluorescence data: np.ndarray
        Fluorescence data matrix (cells x time)
    output_dir : str
        Directory for saving output files
    params : dict, optional
        Dictionary of parameters for PCA analysis
    ts_file : str, optional
        Path to trial structure file for trial averaging
    **kwargs : dict
        Additional keyword arguments

    Returns
    -------
    dict
        Dictionary containing analysis results
    """

    # Get the fluorescence data
    n_cells = fluorescence.shape[0]

    # # If iscell data is available, use it to filter fluorescence
    # if "iscell" in cnmf_info and cnmf_info["iscell"] is not None:
    #     iscell = cnmf_info["iscell"].data
    #     if len(iscell) == fluorescence.shape[0]:
    #         good_indices = np.where(iscell == 1)[0]
    #         logger.info(f"Using only iscell {len(good_indices)} ROI for KMeans")

    #         if len(good_indices) > 0:
    #             # Filter fluorescence to only include good components
    #             fluorescence = fluorescence[good_indices]

    # Get data shape
    n_cells = fluorescence.shape[0]
    logger.info(
        f"PCA: fluorescence shape is {fluorescence.shape}, so n_cells = {n_cells}"
    )

    # Check if we have enough ROIs for PCA
    if n_cells < 2:
        logger.warning("Not enough cells for PCA analysis (minimum 2 required)")
        # Create dummy placeholders
        dummy_scores = np.zeros((1, 1))
        dummy_scores_ave = np.zeros((1, 1))
        dummy_components = np.zeros((1, 1))
        dummy_explained_variance = np.zeros(1)

        # Store results in StatData
        stat.pca_scores = dummy_scores
        stat.pca_scores_ave = dummy_scores_ave
        stat.pca_components = dummy_components
        stat.pca_explained_variance = dummy_explained_variance

        # Store ROI masks for visualization
        stat.roi_masks = roi_masks

        # Still create visualization objects for proper UI display
        stat.set_pca_props()

        # Add message to nwbfile
        nwbfile = kwargs.get("nwbfile", {})
        pca_dict = {
            "pca_scores": dummy_scores,
            "pca_scores_ave": dummy_scores_ave,
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
    logger.info(f"PCA will use {n_cells} cells")

    # Set default parameters if none provided
    if params is None:
        params = {"n_components": min(n_cells, 50), "standard_norm": True}
    else:
        # Extract parameters from the nested structure if present
        pca_params = params.get("PCA", {})

        # Use min(n_cells, 50) as the default when the key is missing from parameters
        params = {
            "n_components": min(
                pca_params.get("n_components", min(n_cells, 50)), n_cells
            ),
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
    pca = PCA(n_components=params["n_components"], svd_solver="randomized")
    scores = pca.fit_transform(data.T)  # time x components
    components = pca.components_  # components x cells
    explained_variance = pca.explained_variance_ratio_ * 100

    if len(explained_variance) > 1:
        # Get indices sorted by explained variance (descending)
        sort_idx = np.argsort(explained_variance)[::-1]

        # Reorder results
        scores = scores[:, sort_idx]
        components = components[sort_idx]
        explained_variance = explained_variance[sort_idx]

    # Initialize variables for trial-averaging
    scores_ave = None

    # Create an ExpDbData object with the trial structure file
    expdb = ExpDbData(paths=[ts_file])
    ts_data = expdb.ts
    logger.info(f"Successfully loaded trial structure data from {ts_file}")

    try:
        stim_log = ts_data.stim_log
        n_frames = fluorescence.shape[1]

        # Check if stim_log exists and calculate dimensions
        if stim_log is not None and len(stim_log) > 0:
            n_stims = int(np.max(stim_log)) + 1

            # Calculate and use only complete trials
            complete_trials = len(stim_log) // n_stims
            n_components = scores.shape[1]

            if complete_trials > 0:
                n_trials = complete_trials
                # Use only the portion of stim_log that contains complete trials
                usable_stim_log = stim_log[: n_stims * n_trials]

                # Calculate frame dimensions
                n_frames_ave = n_frames // n_trials
                n_frames_epoch = n_frames_ave // n_stims

                # Verify frame dimensions are compatible
                if n_frames_epoch * n_stims * n_trials <= n_frames:
                    # Now do reshaping with verified dimensions
                    stim_matrix = np.reshape(usable_stim_log, (n_stims, n_trials))
                    sort_idx_log = np.argsort(stim_matrix, axis=1).ravel() + np.repeat(
                        np.arange(0, n_stims), n_trials
                    )

                    # Only use the portion of scores in complete trials
                    usable_frames = n_frames_epoch * n_stims * n_trials
                    scores_sort = np.reshape(
                        scores[:usable_frames],
                        (n_frames_epoch, n_stims * n_trials, n_components),
                    )[:, sort_idx_log, :]

                    # Final reshape and average as in original code
                    scores_ave = np.mean(
                        np.reshape(
                            scores_sort,
                            (n_frames_epoch * n_stims, n_trials, n_components),
                        ),
                        axis=1,
                    )

                    logger.info(f"Trial-averaged PCA scores shape: {scores_ave.shape}")
                else:
                    logger.warning(
                        f"Dimensions mismatch: n_frames_epoch({n_frames_epoch}) "
                        f"* n_stims({n_stims}) * n_trials({n_trials}) > "
                        f"n_frames({n_frames})"
                    )
            else:
                logger.warning(
                    f"No complete trials available "
                    f"(n_stims={n_stims}, stim_log length={len(stim_log)})"
                )
        else:
            logger.warning("No stim_log data available in trial structure")
    except Exception as e:
        logger.error(f"Error computing trial-averaged PCA scores: {e}")

    # Store results in StatData
    stat.pca_scores = scores
    stat.pca_scores_ave = scores_ave
    stat.pca_components = components
    stat.pca_explained_variance = explained_variance

    # Store ROI masks for visualization
    # Request from client to use data not filtered by iscell
    stat.roi_masks = roi_masks

    # Create visualization objects within the function
    stat.set_pca_props()

    # Add to nwbfile if needed
    nwbfile = kwargs.get("nwbfile", {})
    pca_dict = {
        "pca_scores": scores,
        "pca_scores_ave": scores_ave,
        "pca_components": components,
        "pca_explained_variance": explained_variance,
    }
    nwbfile = {
        NWBDATASET.ORISTATS: {**nwbfile.get(NWBDATASET.ORISTATS, {}), **pca_dict}
    }

    return {
        "stat": stat,
        "nwbfile": nwbfile,
    }


def generate_pca_visualization(
    scores,
    explained_variance,
    components,
    roi_masks,
    scores_ave,
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
                _ = count
                # logger.info(f"  ROI ID {val}: {count} pixels")
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
        contrib_path = join_filepath([output_dir, "pca_contribution_001.png"])
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
        spatial_path = join_filepath([output_dir, "pca_component_spatial_001.png"])
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
        time_path = join_filepath([output_dir, "pca_component_time_001.png"])
        plt.savefig(time_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(time_path)

        return

    # Number of components to visualize
    num_components = min(50, components.shape[0], scores.shape[1])

    # Set to 20 as too many make legend illegible
    plots_to_show = 20

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

    # For each component
    for i in range(num_components):
        # 2. Time course plots - trial-averaged scores are available
        if scores_ave is not None and scores_ave.shape[1] > i:
            plt.figure()
            plt.plot(scores_ave[:, i], linewidth=2)
            plt.title(f"PC {i+1} Trial-Averaged Time Course")
            plt.xlabel("Time")
            plt.ylabel("Component Value")
            plt.grid(True, alpha=0.3)
            time_path = join_filepath([output_dir, f"pca_component_time_{i+1:03d}.png"])
            plt.savefig(time_path, bbox_inches="tight")
            plt.close()
            save_thumbnail(time_path)

        else:
            plt.figure()
            plt.plot(scores[:, i], linewidth=2)
            plt.title(f"PC {i+1} Time Courses (All Trials)")
            plt.xlabel("Time")
            plt.ylabel("Component Value")
            plt.grid(True, alpha=0.3)

            time_path = join_filepath([output_dir, f"pca_component_time_{i+1:03d}.png"])
            plt.savefig(time_path, bbox_inches="tight")
            plt.close()
            save_thumbnail(time_path)

        # 3. Spatial map - attempt only if roi_masks has appropriate shape
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
                            [output_dir, f"pca_component_spatial_{i+1:03d}.png"]
                        )
                        plt.grid(True, alpha=0.3)
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
                    [output_dir, f"pca_component_spatial_{i+1:03d}.png"]
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
                [output_dir, f"pca_component_spatial_{i+1:03d}.png"]
            )
            plt.savefig(spatial_path, bbox_inches="tight")
            plt.close()
            save_thumbnail(spatial_path)

    # 4. Save the contribution weights with PCA components
    # Calculate how many plots we need based on the number of cells
    logger.info(f"Components shape: {components.shape}")
    logger.info(f"Number of scores dimensions: {scores.shape[1]}")
    logger.info(f"Explained variance values: {len(explained_variance)}")

    n_components = components.shape[0]
    components_per_plot = 20
    n_plots = int(np.ceil(n_components / components_per_plot))
    logger.info(f"Number of plots: {n_plots}")

    # Extract actual cell IDs from roi_masks
    cell_ids = []
    if roi_masks is not None and hasattr(roi_masks, "shape"):
        try:
            # Extract non-NaN values from roi_masks
            non_nan_mask = (
                ~np.isnan(roi_masks)
                if np.any(np.isnan(roi_masks))
                else np.ones_like(roi_masks, dtype=bool)
            )

            if np.any(non_nan_mask):
                # Get unique cell IDs
                valid_ids = np.unique(roi_masks[non_nan_mask])
                cell_ids = list(np.sort(valid_ids))
                logger.info(f"Found {len(cell_ids)} unique cell IDs in ROI masks")
            else:
                logger.warning("No valid values in ROI masks for cell ID extraction")
        except Exception as e:
            logger.error(f"Error extracting cell IDs from ROI masks: {str(e)}")

    # If we couldn't extract cell IDs, use sequential numbering
    if not cell_ids:
        cell_ids = list(range(components.shape[1]))
        logger.info("Using sequential numbering for cell IDs")

    # Sort components by explained variance (descending)
    if explained_variance is not None and len(explained_variance) == n_components:
        # Get indices sorted by explained variance
        sorted_indices = np.argsort(explained_variance)[::-1]
        # Reorder components based on sorted indices
        sorted_components = components[sorted_indices]
        # Create mapping from new indices to original indices
        sorted_to_original = {i: sorted_indices[i] for i in range(len(sorted_indices))}
        logger.info("Sorted components by explained variance")
    else:
        sorted_components = components
        sorted_to_original = {i: i for i in range(n_components)}
        logger.warning("Could not sort components by variance - using original order")

    for plot_idx in range(n_plots):
        start_idx = plot_idx * components_per_plot
        end_idx = min(start_idx + components_per_plot, n_components)

        logger.info(
            f"Contribution plot {plot_idx+1}: components {start_idx+1} to {end_idx}"
        )

        if start_idx >= n_components:
            logger.warning(
                f"Skipping plot {plot_idx+1} - start_idx {start_idx}"
                f">= n_components {n_components}"
            )
            break

        plt.figure()

        # Get the components for this plot
        plot_components = sorted_components[start_idx:end_idx]
        n_cells = len(plot_components[0])

        # Create x-axis labels for the PCA components
        x_labels = [
            f"PC {sorted_to_original[start_idx + i] + 1}"
            for i in range(len(plot_components))
        ]
        x_positions = np.arange(len(x_labels))

        # Calculate the total contribution magnitude for each cell
        cell_total_contributions = []
        for cell_idx in range(n_cells):
            # Get this cell's contribution to each component in this plot
            cell_contributions = [comp[cell_idx] for comp in plot_components]
            # Use sum of absolute values to measure total contribution
            total_contribution = sum(abs(c) for c in cell_contributions)
            cell_total_contributions.append((cell_idx, total_contribution))

        # Sort cells by their total contribution (descending)
        sorted_cells = sorted(
            cell_total_contributions, key=lambda x: x[1], reverse=True
        )

        # Limit to top 20 contributing cells for readability
        top_cells = sorted_cells[:20]

        # For each of the top contributing cells, plot its contribution
        for rank, (cell_idx, _) in enumerate(top_cells):
            # Get this cell's contribution to each component in this plot
            cell_contributions = [comp[cell_idx] for comp in plot_components]

            # Get the actual cell ID
            cell_id = cell_ids[cell_idx] if cell_idx < len(cell_ids) else cell_idx
            if isinstance(cell_id, (int, float)) and not np.isnan(cell_id):
                cell_id_label = f"ROI {int(cell_id)}"
            else:
                cell_id_label = f"ROI {cell_id}"

            # Plot the bar for this cell
            plt.bar(
                x_positions,
                cell_contributions,
                label=cell_id_label,  # Use actual cell ID in legend
                width=0.8,
                alpha=0.7,
            )

        # Add horizontal line at y=0
        plt.axhline(y=0, color="black", linestyle="-", linewidth=1)

        # Add labels and title
        plt.xlabel("PCA Components (Sorted by Explained Variance)")
        plt.ylabel("Cell Contribution")

        plt.title(f"PCA Components {start_idx+1} to {end_idx} and Cell Contributions")

        plt.xticks(x_positions, x_labels, rotation=45)
        plt.tight_layout()
        plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

        # Save the figure
        contrib_path = join_filepath(
            [output_dir, f"pca_contribution_{plot_idx+1:03d}.png"]
        )
        plt.savefig(contrib_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(contrib_path)

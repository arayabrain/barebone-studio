import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.dataclass.utils import save_thumbnail
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass.expdb import ExpDbData
from studio.app.optinist.dataclass.stat import StatData

logger = AppLogger.get_logger()


def kmeans_analysis(
    stat: StatData,
    roi_masks: np.ndarray,
    fluorescence: np.ndarray,
    output_dir: str,
    params: dict = None,
    ts_file=None,
    **kwargs,
) -> dict:
    """
    Perform KMeans clustering analysis on CNMF results with trial structure support

    Parameters
    ----------
    stat : StatData
        StatData object to store analysis results
    roi_masks data: np.ndarray
    output_dir : str
        Directory for saving output files
    params : dict, optional
        Dictionary of parameters for KMeans clustering
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

    # Set default parameters if none provided
    if params is None:
        params = {"n_clusters": min(10, n_cells)}
    else:
        # Extract parameters from the nested structure if present
        kmeans_params = params.get("kmeans", {})

        # Use min(10, n_cells) as the default when the key is missing
        n_clusters = kmeans_params.get("n_clusters", min(10, n_cells))

        # Ensure n_clusters is valid
        params = {
            "n_clusters": min(n_clusters, n_cells),
        }

    # Handle case when there are insufficient cells for clustering
    if n_cells < 2:
        # Set dummy values
        cluster_labels = np.zeros(max(1, n_cells), dtype=int)
        corr_matrix = np.ones((max(1, n_cells), max(1, n_cells)), dtype=float)

        # Initialize dictionaries with dummy values
        all_labels = {"optimal": cluster_labels, "minus_1": None, "plus_1": None}
        all_sorted_matrices = {"optimal": corr_matrix, "minus_1": None, "plus_1": None}

        # Store results in StatData
        stat.cluster_labels = cluster_labels
        stat.cluster_corr_matrix = corr_matrix
        stat.silhouette_scores = None
        stat.optimal_clusters = 1
        stat.all_labels = all_labels
        stat.all_sorted_matrices = all_sorted_matrices

        # Store data needed for visualization
        stat.fluorescence = fluorescence
        stat.fluorescence_ave = np.zeros((1, 1))
        stat.roi_masks = roi_masks

        # Create visualization objects within the function
        stat.set_kmeans_props()

        # Add to nwbfile if needed
        nwbfile = kwargs.get("nwbfile", {})
        clustering_dict = {
            "cluster_labels": cluster_labels,
            "cluster_corr_matrix": corr_matrix,
            "silhouette_scores": None,
            "optimal_clusters": 1,
        }
        nwbfile = {
            NWBDATASET.ORISTATS: {
                **nwbfile.get(NWBDATASET.ORISTATS, {}),
                **clustering_dict,
            }
        }

        return {
            "stat": stat,
            # "cluster_corr_matrix": stat.cluster_corr_matrix,
            "nwbfile": nwbfile,
        }
    logger.info(f"KMeans will use {n_cells} cells")

    # Perform Kmeans clustering
    # Compute correlation matrix
    corr_matrix = np.corrcoef(fluorescence)

    # Test clusters from 2 to 30 (or maximum cells if less)
    k_range = range(2, min(31, n_cells))
    silhouette_values = []
    cluster_labels_list = []

    # Calculate silhouette score for each number of clusters
    for k in k_range:
        kmeans_temp = KMeans(
            n_clusters=k,
            init="k-means++",
            n_init=5,
            max_iter=100,
            tol=1e-3,
            random_state=42,
            algorithm="elkan",
        )
        labels_temp = kmeans_temp.fit_predict(corr_matrix)
        cluster_labels_list.append(labels_temp)
        # Only calculate silhouette if we have at least 2 clusters and enough samples
        if k >= 2 and n_cells > k:
            try:
                sil_score = silhouette_score(corr_matrix, labels_temp)
                silhouette_values.append(sil_score)
            except Exception as e:
                logger.warning(f"Silhouette calculation failed for k={k}: {e}")
                silhouette_values.append(-1)  # Use negative value to mark failure
        else:
            silhouette_values.append(-1)

    # Find optimal number of clusters (if silhouette calculation succeeded)
    if any(score > 0 for score in silhouette_values):
        best_k_idx = np.argmax(silhouette_values)
        k_optimal = k_range[best_k_idx]
        cluster_labels = cluster_labels_list[best_k_idx]
    else:
        # Fallback to default if silhouette calculation failed
        k_optimal = min(params.get("n_clusters", 3), n_cells)
        kmeans = KMeans(
            n_clusters=k_optimal, init="k-means++", n_init=10, algorithm="elkan"
        )
        cluster_labels = kmeans.fit_predict(corr_matrix)

    # Initialize dictionaries for different k values
    all_sorted_matrices = {"optimal": None, "minus_1": None, "plus_1": None}
    all_labels = {"optimal": None, "minus_1": None, "plus_1": None}

    # Create sorted correlation matrix for optimal k
    sort_idx = np.argsort(cluster_labels)
    all_sorted_matrices["optimal"] = corr_matrix[sort_idx][:, sort_idx]
    all_labels["optimal"] = cluster_labels

    # Create matrices for k-1 and k+1 if possible
    if k_optimal > 2:
        kmeans_minus1 = KMeans(
            n_clusters=k_optimal - 1,
            init="k-means++",
            n_init=10,
            random_state=42,
            algorithm="elkan",
        )
        labels_minus1 = kmeans_minus1.fit_predict(corr_matrix)
        all_labels["minus_1"] = labels_minus1
        sort_idx_minus1 = np.argsort(labels_minus1)
        all_sorted_matrices["minus_1"] = corr_matrix[sort_idx_minus1][
            :, sort_idx_minus1
        ]

    # Create sorted correlation matrix for k+1 (if k < max_k)
    if k_optimal < n_cells - 1:
        kmeans_plus1 = KMeans(
            n_clusters=k_optimal + 1,
            init="k-means++",
            n_init=10,
            random_state=42,
            algorithm="elkan",
        )
        labels_plus1 = kmeans_plus1.fit_predict(corr_matrix)
        all_labels["plus_1"] = labels_plus1
        sort_idx_plus1 = np.argsort(labels_plus1)
        all_sorted_matrices["plus_1"] = corr_matrix[sort_idx_plus1][:, sort_idx_plus1]

    # Store results in StatData
    stat.cluster_labels = all_labels["optimal"]
    stat.cluster_corr_matrix = all_sorted_matrices["optimal"]
    stat.all_labels = all_labels
    stat.all_sorted_matrices = all_sorted_matrices
    stat.silhouette_scores = silhouette_values
    stat.optimal_clusters = k_optimal

    # Trial averaging
    # Initialize variables for trial-averaged fluorescence
    fluorescence_ave = None
    ts_data = None

    # Create an ExpDbData object with the trial structure file
    expdb = ExpDbData(paths=[ts_file])
    ts_data = expdb.ts
    logger.info(f"Successfully loaded trial structure data from {ts_file}")

    # Compute trial-averaged fluorescence
    try:
        stim_log = ts_data.stim_log
        n_frames = fluorescence.shape[1]

        # Check if stim_log exists and calculate dimensions
        if stim_log is not None and len(stim_log) > 0:
            n_stims = int(np.max(stim_log)) + 1

            # Calculate and use only complete trials
            complete_trials = len(stim_log) // n_stims

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

                    # Initialize trial-averaged fluorescence array
                    fluorescence_ave = np.zeros((n_cells, n_frames_epoch * n_stims))

                    # Process each cell
                    for cell_idx in range(n_cells):
                        # Get the cell's fluorescence data (usable frames)
                        usable_frames = n_frames_epoch * n_stims * n_trials
                        cell_fluo = fluorescence[cell_idx, :usable_frames]

                        # Reshape to (n_frames_epoch, n_stims * n_trials)
                        cell_fluo_reshape = np.reshape(
                            cell_fluo, (n_frames_epoch, n_stims * n_trials)
                        )

                        # Sort according to stim_matrix sort_idx_log
                        cell_fluo_sort = cell_fluo_reshape[:, sort_idx_log]

                        # Reshape for trial averaging
                        cell_fluo_3d = np.reshape(
                            cell_fluo_sort, (n_frames_epoch, n_stims, n_trials)
                        )

                        # Average across trials
                        # (keeping n_frames_epoch and n_stims dimensions)
                        cell_fluo_avg = np.mean(
                            cell_fluo_3d, axis=2
                        )  # (n_frames_epoch, n_stims)

                        # Reshape to flatten time dimension
                        # (n_frames_epoch * n_stims)
                        fluorescence_ave[cell_idx] = np.reshape(cell_fluo_avg, -1)

                    logger.info(f"Trial-averaged fluo shape: {fluorescence_ave.shape}")
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
        logger.error(f"Error computing trial-averaged fluorescence: {e}")

    # Store data needed for visualization
    stat.fluorescence = fluorescence
    stat.fluorescence_ave = fluorescence_ave
    # Request from client to use data not filtered by iscell
    stat.roi_masks = roi_masks

    # Create visualization objects within the function
    stat.set_kmeans_props()

    # Add to nwbfile if needed
    nwbfile = kwargs.get("nwbfile", {})
    clustering_dict = {
        "cluster_labels": cluster_labels,
        "cluster_corr_matrix": corr_matrix,
        "silhouette_scores": silhouette_values,
        "optimal_clusters": k_optimal,
    }
    nwbfile = {
        NWBDATASET.ORISTATS: {**nwbfile.get(NWBDATASET.ORISTATS, {}), **clustering_dict}
    }

    return {
        "stat": stat,
        "nwbfile": nwbfile,
    }


def generate_kmeans_visualization(
    all_labels,
    all_sorted_matrices,
    fluorescence,
    roi_masks,
    silhouette_scores,
    optimal_clusters,
    fluorescence_ave,
    output_dir,
):
    """
    Generate KMeans visualizations with separate files for each component

    Parameters
    ----------
    all_labels : dict
        Dictionary of cluster assignments for each k value:
        ("optimal", "minus_1", "plus_1")
    all_sorted_matrices : dict
        Dictionary of sorted correlation matrices for each k value
    fluorescence : ndarray
        Temporal components/fluorescence traces (n_cells x time)
    roi_masks : ndarray or None
        ROI masks data in any format
    silhouette_scores : ndarray, optional
        Silhouette scores for different numbers of clusters
    optimal_clusters : int, optional
        Optimal number of clusters based on silhouette analysis
    fluorescence_ave : ndarray, optional
        Trial-averaged fluorescence data (n_cells x time)
    output_dir : str
        Directory for saving output files
    """
    # Handle the case of insufficient ROIs
    corr_matrix = all_sorted_matrices.get("optimal")
    labels = all_labels.get("optimal")

    is_data_insufficient = (
        all_labels is None
        or "optimal" not in all_labels
        or all_labels["optimal"] is None
        or len(all_labels["optimal"]) < 2
        or corr_matrix is None
        or corr_matrix.shape[0] < 2
    )

    if is_data_insufficient:
        # Create error image for correlation matrix plot
        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for k-means clustering.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        matrix_path = join_filepath([output_dir, "clustering_analysis_001.png"])
        plt.savefig(matrix_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(matrix_path)

        # Create error image for time courses plot
        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for k-means clustering.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        time_path = join_filepath([output_dir, "cluster_time_courses.png"])
        plt.savefig(time_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(time_path)

        # Create error image for spatial map
        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for k-means clustering.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        map_path = join_filepath([output_dir, "cluster_spatial_map.png"])
        plt.savefig(map_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(map_path)

        plt.figure()
        plt.text(
            0.5,
            0.5,
            "Insufficient ROIs for k-means clustering.\nAt least 2 ROIs required.",
            ha="center",
            va="center",
            transform=plt.gca().transAxes,
        )
        plt.axis("off")
        silhouette_path = join_filepath([output_dir, "cluster_silhouette_scores.png"])
        plt.savefig(silhouette_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(silhouette_path)

        return

    # 1. Plot silhouette scores for determining optimal number of clusters
    if silhouette_scores is not None and len(silhouette_scores) > 0:
        plt.figure()
        k_range = range(2, 2 + len(silhouette_scores))

        # Filter out negative values (failed calculations)
        valid_indices = [i for i, score in enumerate(silhouette_scores) if score >= 0]
        valid_k = [k_range[i] for i in valid_indices]
        valid_scores = [silhouette_scores[i] for i in valid_indices]

        if len(valid_scores) > 0:
            plt.plot(valid_k, valid_scores, "o-", linewidth=2)

            # Highlight the optimal cluster
            if optimal_clusters is not None and optimal_clusters in valid_k:
                opt_idx = valid_k.index(optimal_clusters)
                plt.plot(
                    optimal_clusters,
                    valid_scores[opt_idx],
                    "o",
                    markersize=10,
                    markerfacecolor="red",
                    markeredgecolor="black",
                )
                plt.axvline(x=optimal_clusters, color="gray", linestyle="--", alpha=0.7)

            # Create double-line title with optimal cluster information
            main_title = "Silhouette Score Analysis for K-means Clustering"
            if optimal_clusters is not None:
                subtitle = f"Optimal number of clusters: {optimal_clusters}"
                plt.title(f"{main_title}\n{subtitle}")
            else:
                plt.title(main_title)

            plt.xlabel("Number of Clusters (k)")
            plt.ylabel("Silhouette Score")
            plt.grid(True, alpha=0.3)
            plt.xticks(valid_k)  # Show all tested k values on x-axis
            plt.axis("on")

            silhouette_path = join_filepath(
                [output_dir, "cluster_silhouette_scores.png"]
            )
            plt.savefig(silhouette_path, bbox_inches="tight")
            plt.close()
            save_thumbnail(silhouette_path)

    # 2. Plot correlation matrices for optimal, k-1, and k+1
    # Loop through each matrix type in all_sorted_matrices
    for key in ["optimal", "minus_1", "plus_1"]:
        matrix = all_sorted_matrices.get(key)
        if matrix is None:
            continue  # Skip if the matrix is not present or is None

        labels = all_labels.get(key)
        if labels is None:
            continue  # Skip if no labels for this k value

        # Calculate cluster information
        unique_clusters = np.unique(labels)
        n_clusters = len(unique_clusters)
        colors = plt.cm.jet(np.linspace(0, 1, n_clusters))

        # Determine k and title based on the key
        if key == "optimal":
            if optimal_clusters is not None:
                k = optimal_clusters
                title = f"K-means Clustering k={k} (Optimal)"
            else:
                k = n_clusters
                title = f"K-means Clustering (k={k}) (Default )"
        elif key == "minus_1":
            k = optimal_clusters - 1
            title = f"K-means Clustering k={k} (Optimal k-1)"
        elif key == "plus_1":
            k = optimal_clusters + 1
            title = f"K-means Clustering k={k} (Optimal k+1)"

        # Determine the output filename
        if key == "optimal":
            filename = "clustering_analysis_001.png"
        elif key == "minus_1":
            filename = "clustering_analysis_002.png"
        elif key == "plus_1":
            filename = "clustering_analysis_003.png"

        # Create and save the plot
        plt.figure()
        im = plt.imshow(matrix, cmap="viridis")
        plt.colorbar(im)
        plt.title(title)
        plt.xlabel("Cells")
        plt.ylabel("Cells")

        output_path = join_filepath([output_dir, filename])
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(output_path)

    # 3. Mean time courses by cluster (using optimal k labels)
    labels = all_labels.get("optimal")
    if (
        labels is not None
        and (fluorescence is not None or fluorescence_ave is not None)
        and (
            (fluorescence is not None and fluorescence.shape[0] >= len(labels))
            or (
                fluorescence_ave is not None
                and fluorescence_ave.shape[0] >= len(labels)
            )
        )
    ):
        unique_clusters = np.unique(labels)
        n_clusters = len(unique_clusters)
        colors = plt.cm.jet(np.linspace(0, 1, n_clusters))

        # Choose which fluorescence data to use
        fluo_data = fluorescence_ave if fluorescence_ave is not None else fluorescence
        time_course_type = (
            "Trial-Averaged" if fluorescence_ave is not None else "All Trials"
        )

        for i, cluster in enumerate(unique_clusters):
            plt.figure()
            cluster_mask = labels == cluster

            if np.any(cluster_mask):
                cluster_avg = np.mean(fluo_data[cluster_mask], axis=0)
                plt.plot(cluster_avg, linewidth=2, color=colors[i])

                # Add individual cell traces with lower alpha
                for cell_idx in np.where(cluster_mask)[0]:
                    plt.plot(fluo_data[cell_idx], alpha=0.2, linewidth=0.5)

                plt.title(f"Cluster {i+1} {time_course_type} Time Course")
                plt.xlabel("Time")
                plt.ylabel("Fluorescence")
                plt.grid(True, alpha=0.3)

                # Save individual time course plot
                single_time_path = join_filepath(
                    [output_dir, f"cluster_time_course_{i+1:03d}.png"]
                )
                plt.savefig(single_time_path, bbox_inches="tight")
                plt.close()
                save_thumbnail(single_time_path)

    # 4. Spatial cluster map - attempt only if roi_masks has appropriate shape
    if roi_masks is not None and hasattr(roi_masks, "shape") and labels is not None:
        try:
            # Create cluster colormap
            unique_clusters = np.unique(labels)
            n_clusters = len(unique_clusters)
            colors = plt.cm.jet(np.linspace(0, 1, n_clusters))

            logger.info(f"Unique clusters: {unique_clusters}")

            # Create individual plots for each cluster
            for i, cluster_id in enumerate(unique_clusters):
                plt.figure()

                # Count cells in this cluster
                cluster_indices = np.where(labels == cluster_id)[0]
                cells_in_cluster = len(cluster_indices)
                logger.info(f"cluster_indices : {cluster_indices}")
                logger.info(f"Cluster {i+1} contains {cells_in_cluster} cells")
                logger.info(f"roi_masks.shape: {roi_masks.shape}")

                # Create a binary mask of all ROIs for background
                roi_binary_mask = (
                    ~np.isnan(roi_masks)
                    if np.any(np.isnan(roi_masks))
                    else roi_masks > 0
                )

                # Show all ROIs in light gray
                white_cmap = ListedColormap(["white"])
                plt.imshow(roi_binary_mask, cmap=white_cmap, alpha=0.2)

                # Create a mask for only the cells in this cluster
                cluster_mask = np.zeros_like(roi_masks, dtype=bool)

                # Find unique cell IDs in roi_masks
                valid_mask = (
                    ~np.isnan(roi_masks)
                    if np.any(np.isnan(roi_masks))
                    else roi_masks > 0
                )
                unique_ids = np.unique(roi_masks[valid_mask])

                # Check if we have any overlap between cluster indices and cell IDs
                cell_id_matching = any(
                    cell_id in cluster_indices for cell_id in unique_ids
                )

                # Try direct matching first if it seems valid
                if cell_id_matching:
                    # The cell IDs themselves match cluster indices
                    for cell_id in unique_ids:
                        if cell_id in cluster_indices:
                            cell_mask = np.isclose(roi_masks, cell_id)
                            cluster_mask = cluster_mask | cell_mask

                    # Check if any cells - if not, fall back to position mapping
                    if not np.any(cluster_mask):
                        cell_id_matching = False

                # If direct matching failed or found no cells, use position mapping
                if not cell_id_matching:
                    index_to_cell_id = {
                        idx: cell_id for idx, cell_id in enumerate(unique_ids)
                    }
                    for idx in cluster_indices:
                        if idx < len(unique_ids):
                            cell_id = index_to_cell_id[idx]
                            cell_mask = np.isclose(roi_masks, cell_id)
                            cluster_mask = cluster_mask | cell_mask

                # Create colored overlay for this cluster's cells only
                colored_overlay = np.zeros((*roi_masks.shape, 4))  # RGBA
                colored_overlay[cluster_mask, :3] = colors[
                    i, :3
                ]  # RGB from cluster color
                colored_overlay[cluster_mask, 3] = 0.7  # Alpha for transparency
                plt.imshow(colored_overlay)

                plt.title(f"Cluster {i+1} ({cells_in_cluster} cells)")
                plt.grid(True, alpha=0.3)

                # Save individual cluster map
                single_map_path = join_filepath(
                    [output_dir, f"cluster_spatial_map_{i+1:03d}.png"]
                )
                plt.savefig(single_map_path, bbox_inches="tight")
                plt.close()
                save_thumbnail(single_map_path)

        except Exception as e:
            logger.warning(f"Could not create cluster spatial map: {str(e)}")

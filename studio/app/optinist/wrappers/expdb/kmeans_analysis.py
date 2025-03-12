import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.dataclass.utils import save_thumbnail
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass.stat import StatData

logger = AppLogger.get_logger()


def kmeans_analysis(
    stat: StatData, cnmf_info: dict, output_dir: str, params: dict = None, **kwargs
) -> dict:
    """Perform KMeans clustering analysis on CNMF results"""

    # Get the fluorescence data
    fluorescence = cnmf_info["fluorescence"].data

    # If iscell data is available, use it to filter fluorescence
    if "iscell" in cnmf_info and cnmf_info["iscell"] is not None:
        iscell = cnmf_info["iscell"].data
        if len(iscell) == fluorescence.shape[0]:
            good_indices = np.where(iscell == 1)[0]
            logger.info(f"Using only iscell {len(good_indices)} ROI for KMeans")

            if len(good_indices) > 0:
                # Filter fluorescence to only include good components
                fluorescence = fluorescence[good_indices]

    n_cells = fluorescence.shape[0]
    logger.info(f"KMeans will use {n_cells} cells")

    # Set default parameters if none provided
    if params is None:
        params = {}

    # Handle case when there are insufficient cells for clustering
    if n_cells < 2:
        logger.info("Not enough cells for KMeans clustering (minimum 2 required)")
        # Set dummy values
        cluster_labels = np.zeros(max(1, n_cells), dtype=int)
        corr_matrix = np.ones((max(1, n_cells), max(1, n_cells)), dtype=float)

        # Store results in StatData
        stat.cluster_labels = cluster_labels
        stat.cluster_corr_matrix = corr_matrix
        stat.silhouette_scores = None
        stat.optimal_clusters = 1

        # Store data needed for visualization
        stat.fluorescence = fluorescence
        if not hasattr(stat, "roi_masks") or stat.roi_masks is None:
            stat.roi_masks = cnmf_info["cell_roi"].data

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
            "clustering_analysis": stat.clustering_analysis,
            "nwbfile": nwbfile,
        }

    # Calculate correlation matrix
    corr_matrix = np.corrcoef(fluorescence)

    # Test clusters from 2 to 30 (or maximum cells if less)
    k_range = range(2, min(31, n_cells))
    silhouette_values = []
    cluster_labels_list = []

    # Calculate silhouette score for each number of clusters
    for k in k_range:
        kmeans_temp = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=42)
        labels_temp = kmeans_temp.fit_predict(corr_matrix)
        cluster_labels_list.append(labels_temp)
        # Only calculate silhouette if we have at least 2 clusters and enough samples
        if k >= 2 and n_cells > k:
            try:
                sil_score = silhouette_score(corr_matrix, labels_temp)
                silhouette_values.append(sil_score)
            except Exception as e:
                print(f"Silhouette calculation failed for k={k}: {e}")
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
        kmeans = KMeans(n_clusters=k_optimal, init="k-means++", n_init=10)
        cluster_labels = kmeans.fit_predict(corr_matrix)

    # Store results in StatData
    stat.cluster_labels = cluster_labels
    stat.cluster_corr_matrix = corr_matrix
    stat.silhouette_scores = silhouette_values
    stat.optimal_clusters = k_optimal

    # Store data needed for visualization
    stat.fluorescence = fluorescence
    if not hasattr(stat, "roi_masks") or stat.roi_masks is None:
        stat.roi_masks = cnmf_info["cell_roi"].data

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
        "clustering_analysis": stat.clustering_analysis,
        "nwbfile": nwbfile,
    }


def generate_kmeans_visualization(
    labels,
    corr_matrix,
    fluorescence,
    roi_masks,
    silhouette_scores,
    optimal_clusters,
    output_dir,
):
    """
    Generate KMeans visualizations with separate files for each component

    Parameters
    ----------
    labels : ndarray
        Cluster assignments for each cell
    corr_matrix : ndarray
        Cell-to-cell correlation matrix
    fluorescence : ndarray
        Temporal components/fluorescence traces (n_cells x time)
    roi_masks : ndarray or None
        ROI masks data in any format
    output_dir : str
        Directory for saving output files
    silhouette_scores : ndarray, optional
        Silhouette scores for different numbers of clusters
    optimal_clusters : int, optional
        Optimal number of clusters based on silhouette analysis
    """
    if labels is None or len(labels) == 0:
        logger.warn("Warning: Missing cluster labels")
        return

    # Handle the case of insufficient ROIs
    is_data_insufficient = (
        labels is None
        or len(labels) < 2
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
        matrix_path = join_filepath([output_dir, "clustering_analysis.png"])
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
        silhouette_path = join_filepath([output_dir, "silhouette_scores.png"])
        plt.savefig(silhouette_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(silhouette_path)

        return

    # 1. Plot silhouette scores for determining optimal number of clusters
    if silhouette_scores is not None and len(silhouette_scores) > 0:
        plt.figure(figsize=(10, 6))
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

            plt.title("Silhouette Score Analysis for K-means Clustering")
            plt.xlabel("Number of Clusters (k)")
            plt.ylabel("Silhouette Score")
            plt.grid(True, alpha=0.3)
            plt.xticks(valid_k)  # Show all tested k values on x-axis

            # Add text annotation for optimal cluster
            if optimal_clusters is not None:
                plt.figtext(
                    0.5,
                    0.01,
                    f"Optimal number of clusters: {optimal_clusters}",
                    ha="center",
                    fontsize=12,
                )
        else:
            plt.text(
                0.5,
                0.5,
                "No valid silhouette scores available",
                ha="center",
                va="center",
                transform=plt.gca().transAxes,
            )
            plt.axis("on")

        silhouette_path = join_filepath([output_dir, "silhouette_scores.png"])
        plt.savefig(silhouette_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(silhouette_path)

    # Reorder correlation matrix based on clusters
    sort_idx = np.argsort(labels)
    sorted_corr_matrix = corr_matrix[sort_idx][:, sort_idx]

    # Calculate cluster information
    unique_clusters = np.unique(labels)
    n_clusters = len(unique_clusters)
    colors = plt.cm.jet(np.linspace(0, 1, n_clusters))
    custom_cmap = ListedColormap(colors)

    # 2. Correlation matrix heatmap
    plt.figure()
    im = plt.imshow(sorted_corr_matrix, cmap="jet")
    plt.colorbar(im)
    if optimal_clusters is not None:
        plt.title(f"K-means Clustering k={optimal_clusters}")
    else:
        plt.title(f"K-means Clustering (k={n_clusters})")
    plt.xlabel("Cells")
    plt.ylabel("Cells")

    matrix_path = join_filepath([output_dir, "clustering_analysis.png"])
    plt.savefig(matrix_path, bbox_inches="tight")
    plt.close()
    save_thumbnail(matrix_path)

    # 3. Mean time courses by cluster
    if fluorescence is not None and fluorescence.shape[0] >= len(labels):
        plt.figure()
        cluster_averages = []

        for i, cluster in enumerate(unique_clusters):
            cluster_mask = labels == cluster
            if np.any(cluster_mask):
                cluster_avg = np.mean(fluorescence[cluster_mask], axis=0)
                plt.plot(
                    cluster_avg, color=colors[i], linewidth=2, label=f"Cluster {i+1}"
                )
                cluster_averages.append(cluster_avg)

        plt.title("Mean Time Course by Cluster")
        plt.xlabel("Time")
        plt.ylabel("Fluorescence")
        plt.legend()
        plt.grid(True, alpha=0.3)

        time_path = join_filepath([output_dir, "cluster_time_courses.png"])
        plt.savefig(time_path, bbox_inches="tight")
        plt.close()
        save_thumbnail(time_path)

    # 4. Spatial cluster map - attempt only if roi_masks has appropriate shape
    if roi_masks is not None and hasattr(roi_masks, "shape"):
        try:
            # Create cluster colormap
            unique_clusters = np.unique(labels)
            n_clusters = len(unique_clusters)
            colors = plt.cm.jet(np.linspace(0, 1, n_clusters))
            custom_cmap = ListedColormap(colors)

            # Check for 3D mask (standard case with multiple ROIs)
            if len(roi_masks.shape) == 3:
                cluster_map = np.zeros(roi_masks.shape[:2])

                # Create cluster map
                for i, label in enumerate(labels):
                    if i < roi_masks.shape[2]:
                        roi_mask = roi_masks[:, :, i]
                        cluster_map[roi_mask > 0] = (
                            label + 1
                        )  # +1 to avoid 0 (background)

                # Create a mask of all cell locations
                all_cells_mask = np.zeros(roi_masks.shape[:2], dtype=bool)
                for i in range(roi_masks.shape[2]):
                    all_cells_mask |= roi_masks[:, :, i] > 0

                # Create masked cluster map for better visualization
                masked_cluster_map = np.ma.masked_array(
                    cluster_map,
                    mask=~all_cells_mask,  # Mask background (non-cell areas)
                )

                # Plot cluster map
                plt.figure()
                im = plt.imshow(
                    masked_cluster_map, cmap=custom_cmap, interpolation="nearest"
                )

                # Add colorbar with cluster labels
                colorbar = plt.colorbar(im, ticks=np.arange(1, n_clusters + 1))
                colorbar.set_label("Cluster")

                # Add cluster legend with unique colors
                handles = [
                    plt.Rectangle((0, 0), 1, 1, color=colors[i])
                    for i in range(n_clusters)
                ]
                plt.legend(
                    handles,
                    [f"Cluster {i+1}" for i in range(n_clusters)],
                    loc="upper right",
                    bbox_to_anchor=(1.3, 1),
                )

                plt.title("Cluster Spatial Map")

                # Save maps
                map_path = join_filepath([output_dir, "cluster_spatial_map.png"])
                plt.savefig(map_path, bbox_inches="tight")
                plt.close()
                save_thumbnail(map_path)

            # Simpler 2D mask case
            elif len(roi_masks.shape) == 2:
                cluster_map = np.zeros(roi_masks.shape)
                # Use most common cluster for the mask
                if len(labels) > 0:
                    counts = np.bincount(labels)
                    most_common = np.argmax(counts) if len(counts) > 0 else 0
                    cluster_map[roi_masks > 0] = most_common + 1

                # Plot and save as above
                plt.figure()
                im = plt.imshow(cluster_map, cmap=custom_cmap)
                plt.colorbar(im, label="Cluster")
                plt.title("Cluster Assignments")

                map_path = join_filepath([output_dir, "cluster_spatial_map.png"])
                plt.savefig(map_path, bbox_inches="tight")
                plt.close()
                save_thumbnail(map_path)
        except Exception as e:
            print(f"Could not create cluster spatial map: {str(e)}")

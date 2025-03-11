import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from sklearn.cluster import KMeans

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
                # logger.info(f"Filtered fluorescence shape: {fluorescence.shape}")

    n_cells = fluorescence.shape[0]
    logger.info(f"KMeans will use {n_cells} cells")

    # Set default parameters if none provided
    if params is None:
        params = {}
    # Ensure n_clusters exists and doesn't exceed the number of cells
    params["n_clusters"] = min(params.get("n_clusters", 3), n_cells)

    # Handle case when there are insufficient cells for clustering
    if n_cells < 2:
        logger.warn("Not enough cells for KMeans clustering (minimum 2 required)")
        # Set dummy values
        cluster_labels = np.zeros(max(1, n_cells), dtype=int)
        corr_matrix = np.ones((max(1, n_cells), max(1, n_cells)), dtype=float)

        # Store results in StatData
        stat.cluster_labels = cluster_labels
        stat.cluster_corr_matrix = corr_matrix

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

    # Perform clustering
    kmeans = KMeans(
        n_clusters=params["n_clusters"],
    )
    cluster_labels = kmeans.fit_predict(corr_matrix)

    # Store results in StatData
    stat.cluster_labels = cluster_labels
    stat.cluster_corr_matrix = corr_matrix

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
    labels, corr_matrix, fluorescence, roi_masks, output_dir
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

        return

    # Reorder correlation matrix based on clusters
    sort_idx = np.argsort(labels)
    sorted_corr_matrix = corr_matrix[sort_idx][:, sort_idx]

    # Calculate cluster information
    unique_clusters = np.unique(labels)
    n_clusters = len(unique_clusters)
    colors = plt.cm.jet(np.linspace(0, 1, n_clusters))
    custom_cmap = ListedColormap(colors)

    # 1. Correlation matrix heatmap
    plt.figure()
    im = plt.imshow(sorted_corr_matrix, cmap="jet")
    plt.colorbar(im)
    plt.title(f"K-means Clustering (k={n_clusters})")
    plt.xlabel("Cells")
    plt.ylabel("Cells")

    matrix_path = join_filepath([output_dir, "clustering_analysis.png"])
    plt.savefig(matrix_path, bbox_inches="tight")
    plt.close()
    save_thumbnail(matrix_path)

    # 2. Mean time courses by cluster
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

    # 3. Spatial cluster map - attempt only if roi_masks has appropriate shape
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

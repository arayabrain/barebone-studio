from typing import Optional

import matplotlib.pyplot as plt

from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.json_writer import JsonWriter
from studio.app.common.core.workflow.workflow import OutputPath, OutputType
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.utils import save_thumbnail
from studio.app.common.schemas.outputs import PlotMetaData


class ScatterData(BaseData):
    def __init__(self, data, file_name="scatter", meta: Optional[PlotMetaData] = None):
        super().__init__(file_name)
        self.meta = meta

        assert data.ndim <= 2, "Scatter Dimension Error"

        self.data = data.T

    def save_json(self, json_dir):
        self.json_path = join_filepath([json_dir, f"{self.file_name}.json"])
        JsonWriter.write_as_split(self.json_path, self.data)
        JsonWriter.write_plot_meta(json_dir, self.file_name, self.meta)

    def save_plot(self, output_dir):
        plt.figure()
        plot_data = self.data
        # plot_data = self.data.T

        # If we have 2D data, create a scatter plot
        if plot_data.shape[1] >= 2:
            plt.scatter(plot_data[:, 0], plot_data[:, 1], alpha=0.7)
            plt.xlabel("Component 1")
            plt.ylabel("Component 2")

            # If we have 3D data, use colors to represent the third dimension
            if plot_data.shape[1] >= 3:
                plt.scatter(
                    plot_data[:, 0],
                    plot_data[:, 1],
                    c=plot_data[:, 2],
                    cmap="viridis",
                    alpha=0.7,
                )
                plt.colorbar(label="Component 3")
        else:
            # Fallback for 1D data
            plt.scatter(range(len(plot_data)), plot_data[:, 0], alpha=0.7)
            plt.xlabel("Index")
            plt.ylabel("Value")

        plt.title(f"{self.file_name}")
        plt.grid(True, linestyle="--", alpha=0.7)
        plot_file = join_filepath([output_dir, f"{self.file_name}.png"])
        plt.savefig(plot_file, bbox_inches="tight")
        plt.close()

        save_thumbnail(plot_file)

    @property
    def output_path(self) -> OutputPath:
        return OutputPath(path=self.json_path, type=OutputType.SCATTER)

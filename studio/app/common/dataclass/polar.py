from typing import Optional

# import plotly.express as px
# import plotly.io as pio
import matplotlib.pyplot as plt
import pandas as pd
from numpy import linspace, pi

from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.json_writer import JsonWriter
from studio.app.common.core.workflow.workflow import OutputPath, OutputType
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.utils import save_thumbnail
from studio.app.common.schemas.outputs import PlotMetaData


class PolarData(BaseData):
    def __init__(
        self, data, thetas, file_name="polar", meta: Optional[PlotMetaData] = None
    ):
        # thetas: specify in degrees
        super().__init__(file_name)

        self.data = data
        self.columns = thetas

    def save_json(self, json_dir):
        self.json_path = join_filepath([json_dir, f"{self.file_name}.json"])
        df = pd.DataFrame(self.data, columns=self.columns)
        JsonWriter.write_as_split(self.json_path, df)

    @property
    def output_path(self) -> OutputPath:
        return OutputPath(path=self.json_path, type=OutputType.POLAR)

    def save_plot(self, output_dir):
        for i in range(len(self.data)):
            theta = linspace(0, 2 * pi, len(self.columns))  # Convert theta to radians
            plt.figure()
            ax = plt.subplot(111, polar=True)
            ax.plot(theta, self.data[i])
            ax.set_theta_direction(-1)  # Counterclockwise
            ax.set_theta_offset(pi / 2.0)  # Start angle at 0
            # Close the plot line if needed
            ax.plot(
                [theta[-1], theta[0]],
                [self.data[i][-1], self.data[i][0]],
                linestyle="-",
                linewidth=2,
            )
            plot_file = join_filepath([output_dir, f"{self.file_name}_{i}.png"])
            plt.savefig(plot_file)
            plt.close()
            save_thumbnail(plot_file)

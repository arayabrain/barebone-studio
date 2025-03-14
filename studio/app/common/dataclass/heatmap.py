from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.json_writer import JsonWriter
from studio.app.common.core.workflow.workflow import OutputPath, OutputType
from studio.app.common.dataclass.base import BaseData
from studio.app.common.dataclass.utils import save_thumbnail
from studio.app.common.schemas.outputs import PlotMetaData


class HeatMapData(BaseData):
    def __init__(
        self,
        data,
        columns=None,
        file_name="heatmap",
        meta: Optional[PlotMetaData] = None,
    ):
        super().__init__(file_name)
        self.data = data
        self.meta = meta

        # indexを指定
        if columns is not None:
            self.columns = columns
        else:
            self.columns = np.arange(len(self.data[0]))

    def save_json(self, json_dir):
        self.json_path = join_filepath([json_dir, f"{self.file_name}.json"])
        df = pd.DataFrame(
            self.data,
            columns=self.columns,
        )
        JsonWriter.write_as_split(self.json_path, df)
        JsonWriter.write_plot_meta(json_dir, self.file_name, self.meta)

    def save_plot(self, output_dir):
        plt.figure()
        im = plt.imshow(self.data, cmap="viridis")
        plt.colorbar(im)
        plt.colorbar()
        plot_file = join_filepath([output_dir, f"{self.file_name}.png"])
        plt.savefig(plot_file, bbox_inches="tight")
        plt.close()

        save_thumbnail(plot_file)

    @property
    def output_path(self) -> OutputPath:
        return OutputPath(path=self.json_path, type=OutputType.HEATMAP)

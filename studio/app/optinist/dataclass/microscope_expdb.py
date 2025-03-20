from studio.app.optinist.dataclass.microscope import MicroscopeData


class MicroscopeExpdbData(MicroscopeData):
    def __init__(self, path: str, file_name="microscope_expdb"):
        super().__init__(path, file_name)

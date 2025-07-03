from pydantic import BaseModel


class SnakemakeParams(BaseModel):
    use_conda: bool
    cores: int
    forcetargets: bool
    forceall: bool
    lock: bool

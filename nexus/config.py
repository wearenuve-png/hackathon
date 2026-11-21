"""Carga la configuracion del grupo (empresas, tasas, catalogo, equivalencias, periodos)."""
from .schemas import GroupConfig


def load_group_config(config_dir) -> GroupConfig:
    raise NotImplementedError

"""Flujo completo: ingesta -> conversion -> reglas -> intercompania -> consolidacion."""
from .schemas import RunResult


def run(input_dir, config_dir) -> RunResult:
    raise NotImplementedError

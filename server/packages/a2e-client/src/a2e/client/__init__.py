from importlib.metadata import PackageNotFoundError, version

from .client import AsyncClient, Client

try:
    __version__ = version("a2e-client")
except PackageNotFoundError:
    # PYTHONPATH / source checkout without installed package metadata
    __version__ = "2.3.1"

__all__ = [
    "Client",
    "AsyncClient",
]

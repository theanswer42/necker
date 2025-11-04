import ingestion.amex as amex
import ingestion.bofa as bofa
import ingestion.bofacc as bofacc
import ingestion.chase as chase
import ingestion.discover as discover

_INGESTION_MODULES = {
    "amex": amex,
    "bofa": bofa,
    "bofacc": bofacc,
    "chase": chase,
    "discover": discover,
}


def get_ingestion_module(module_name: str):
    """Get an ingestion module by name."""
    if module_name not in _INGESTION_MODULES:
        raise ValueError(f"Unknown ingestion module: {module_name}")
    return _INGESTION_MODULES[module_name]


def get_available_modules():
    """Get list of available ingestion modules."""
    return list(_INGESTION_MODULES.keys())

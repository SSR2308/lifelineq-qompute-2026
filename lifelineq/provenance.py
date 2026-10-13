"""Content-based provenance; filenames never determine cache validity."""
from dataclasses import asdict, is_dataclass
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def versions():
    return {'python':platform.python_version(), **{p:importlib.metadata.version(p) for p in
            ['qiskit', 'qiskit-aer', 'numpy', 'scipy', 'pandas', 'plotly', 'streamlit', 'pytest']}}


def source_hash():
    # Only computational source defines an experiment; changing prose or UI does
    # not change a distribution. Scenarios and full config are hashed separately.
    digest = hashlib.sha256()
    for path in sorted((ROOT/'lifelineq').glob('*.py')):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def cache_key(scenario, config):
    if is_dataclass(config):
        config = asdict(config)
    payload = dict(schema_version=SCHEMA_VERSION, scenario=scenario.to_dict(), config=config,
                   source_hash=source_hash(), versions=versions())
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()

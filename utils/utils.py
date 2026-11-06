"""Configuration loading and project Python script execution."""
import importlib.util
import json
from pathlib import Path

import yaml


def load_config(path):
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    return json.loads(content) if path.suffix == ".json" else yaml.safe_load(content)


def execute_py(path, connection=None, context=None, params=None):
    path = Path(path).resolve()
    spec = importlib.util.spec_from_file_location("warehouse_project_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main(connection, context or {}, params or {})


def prepare_demo(project=None):
    from pipelines.base import PROJECT
    project = project or PROJECT
    return execute_py(project / "pipelines/staging/py/prepare_demo.py",
                      context={"prepare_demo": True, "project": project})

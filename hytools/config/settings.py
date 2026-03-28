import yaml
from pathlib import Path

def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
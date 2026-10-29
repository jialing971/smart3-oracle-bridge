"""配置加载与保存

运行时配置路径：<exe 或 main.py 同级目录>/config/config.json
默认配置路径：  <exe 或 main.py 同级目录>/config/default_config.json
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from src.config.models import AppConfig, TcpConfig, DatabaseConfig, ProtocolConfig, FieldMapping

_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent

CONFIG_DIR = _BASE / "config"
CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "default_config.json"

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]{0,127}$")


def _ensure_config() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        if DEFAULT_CONFIG_PATH.exists():
            shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
        else:
            save_config(AppConfig())


def _validate_config(cfg: AppConfig) -> None:
    if not (1 <= cfg.tcp.port <= 65535):
        raise ValueError(f"TCP 端口非法: {cfg.tcp.port}")
    if cfg.tcp.max_clients < 1:
        raise ValueError("tcp.max_clients 至少为 1")
    if cfg.tcp.buffer_size < 256:
        raise ValueError("tcp.buffer_size 过小")
    if not cfg.database.user or not cfg.database.dsn:
        raise ValueError("database.user / database.dsn 不能为空")
    if not _IDENT_RE.match(cfg.database.schema):
        raise ValueError(f"非法 schema: {cfg.database.schema!r}")
    if not _IDENT_RE.match(cfg.database.table):
        raise ValueError(f"非法 table: {cfg.database.table!r}")
    if not cfg.field_mapping:
        raise ValueError("field_mapping 不能为空")

    seen_index: set = set()
    seen_col: set = set()
    for m in cfg.field_mapping:
        if m.index in seen_index:
            raise ValueError(f"field_mapping 重复的 index: {m.index}")
        if m.column in seen_col:
            raise ValueError(f"field_mapping 重复的 column: {m.column}")
        if not _IDENT_RE.match(m.column):
            raise ValueError(f"非法列名: {m.column!r}")
        seen_index.add(m.index)
        seen_col.add(m.column)

    if cfg.protocol.max_message_bytes < 1024:
        raise ValueError("protocol.max_message_bytes 过小")


def _dict_to_config(d: dict) -> AppConfig:
    tcp = TcpConfig(**d.get("tcp", {}))
    db = DatabaseConfig(**d.get("database", {}))
    proto = ProtocolConfig(**{k: v for k, v in d.get("protocol", {}).items()
                              if k in ProtocolConfig.__dataclass_fields__})
    mappings = [FieldMapping(**m) for m in d.get("field_mapping", [])]
    return AppConfig(
        admin_password_hash=d.get("admin_password_hash", ""),
        tcp=tcp,
        database=db,
        protocol=proto,
        field_mapping=mappings,
    )


def load_config() -> AppConfig:
    _ensure_config()
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    cfg = _dict_to_config(data)
    _validate_config(cfg)
    return cfg


def save_config(cfg: AppConfig) -> None:
    _validate_config(cfg)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "admin_password_hash": cfg.admin_password_hash,
        "tcp": cfg.tcp.__dict__,
        "database": cfg.database.__dict__,
        "protocol": cfg.protocol.__dict__,
        "field_mapping": [m.__dict__ for m in cfg.field_mapping],
    }
    fd, tmp_path = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        Path(tmp_path).replace(CONFIG_PATH)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise

"""统一日志：轮转文件 + GUI（INFO 及以上；高频写入详情见 app.log DEBUG）"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Optional

_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent
LOG_DIR = _BASE / "logs"
LOG_FILE = LOG_DIR / "app.log"

# 单文件最大 10MB，保留 10 个备份（约 100MB）
_FILE_MAX_BYTES = 10 * 1024 * 1024
_FILE_BACKUP_COUNT = 10

_gui_callback: Optional[Callable[[str], None]] = None


class _GuiHandler(logging.Handler):
    """界面日志区：INFO 及以上（连接/启停/写入摘要）；DEBUG 仅写文件"""

    def emit(self, record: logging.LogRecord) -> None:
        if _gui_callback and record.levelno >= logging.INFO:
            _gui_callback(self.format(record))


def setup_logger(level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    fh = RotatingFileHandler(
        LOG_FILE,
        maxBytes=_FILE_MAX_BYTES,
        backupCount=_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)
    root.addHandler(fh)

    gh = _GuiHandler()
    gh.setFormatter(fmt)
    gh.setLevel(logging.INFO)
    root.addHandler(gh)


def set_gui_callback(cb: Optional[Callable[[str], None]]) -> None:
    global _gui_callback
    _gui_callback = cb


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

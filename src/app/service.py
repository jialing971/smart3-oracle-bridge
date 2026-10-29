"""后台服务编排

Service 负责：
- 加载/重新加载配置
- 在后台线程启动/停止 TcpServer
- 对外暴露 start / stop / restart / is_running
- 通过回调把状态变化推给 GUI
"""
import threading
from typing import Callable, Optional

from src.config.loader import load_config, save_config
from src.config.models import AppConfig
from src.tcp.server import TcpServer
from src.utils.logger import get_logger

log = get_logger(__name__)


class Service:
    def __init__(
        self,
        on_status_change: Optional[Callable[[bool, str], None]] = None,
        on_stats: Optional[Callable[[int, str], None]] = None,
    ):
        """
        on_status_change(running: bool, message: str)  — 服务启动/停止时通知 GUI
        on_stats(active_clients: int, last_barcode: str) — 客户端统计通知 GUI
        """
        self._on_status_change = on_status_change
        self._on_stats = on_stats

        self._cfg: AppConfig = load_config()
        self._server: Optional[TcpServer] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    @property
    def config(self) -> AppConfig:
        return self._cfg

    def reload_config(self) -> None:
        self._cfg = load_config()
        log.info("配置已重新加载")

    def save_and_reload(self, cfg: AppConfig) -> None:
        save_config(cfg)
        self._cfg = cfg
        log.info("配置已保存")

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self.is_running:
            log.warning("服务已在运行，忽略重复启动")
            return

        self.reload_config()
        self._server = TcpServer(self._cfg, on_stats=self._on_stats)
        self._thread = threading.Thread(target=self._server.start, daemon=True)
        self._thread.start()
        log.info("服务启动")
        self._notify_status(True, "服务运行中")

    def stop(self) -> None:
        """阻塞停止（在后台线程中调用，勿在主线程直接 join）"""
        if not self.is_running and self._server is None:
            return
        if self._server:
            self._server.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._server = None
        self._thread = None
        log.info("服务已停止")
        self._notify_status(False, "服务已停止")

    def stop_async(self, on_done: Optional[Callable[[], None]] = None) -> None:
        """非阻塞停止，避免 GUI 主线程 join 导致「未响应」"""

        def _worker() -> None:
            try:
                self.stop()
            finally:
                if on_done:
                    # 回调里若操作 Tk，应通过 root.after 切回主线程
                    on_done()

        threading.Thread(target=_worker, name="ServiceStop", daemon=True).start()

    def restart(self) -> None:
        self.stop()
        self.start()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def active_clients(self) -> int:
        return self._server.active_clients if self._server else 0

    # ------------------------------------------------------------------
    def _notify_status(self, running: bool, msg: str) -> None:
        if self._on_status_change:
            try:
                self._on_status_change(running, msg)
            except Exception:
                pass

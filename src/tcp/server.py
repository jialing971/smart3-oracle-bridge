"""TCP 服务端（产线加固）

- 限制最大并发连接（Semaphore）
- 支持报文缓冲 / 可选结束符，避免粘包半包
- 数据库连接失败时正确释放 socket 与计数
- 统计回调节流，降低 GUI 压力
"""
import socket
import threading
import time
from typing import Callable, List, Optional

from src.config.models import AppConfig
from src.db.writer import DbSession, create_session
from src.protocol.parser import parse_line
from src.utils.logger import get_logger

log = get_logger(__name__)

_STATS_INTERVAL_SEC = 0.25


class TcpServer:
    def __init__(self, cfg: AppConfig, on_stats: Optional[Callable[[int, str], None]] = None):
        self._cfg = cfg
        self._on_stats = on_stats
        self._server_sock: Optional[socket.socket] = None
        self._stop_event = threading.Event()
        self._active_clients = 0
        self._lock = threading.Lock()
        self._client_conns: List[socket.socket] = []
        self._slots = threading.Semaphore(cfg.tcp.max_clients)
        self._last_stats_time = 0.0
        self._pending_barcode = ""

    def start(self) -> None:
        tcp = self._cfg.tcp
        self._stop_event.clear()

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((tcp.host, tcp.port))
        self._server_sock.listen(max(tcp.max_clients, 5))
        self._server_sock.settimeout(1.0)

        log.info("TCP 服务已启动，监听 %s:%s（最大连接 %s）", tcp.host, tcp.port, tcp.max_clients)

        while not self._stop_event.is_set():
            try:
                client_conn, client_addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            if not self._slots.acquire(blocking=False):
                log.warning("已达最大连接数 %s，拒绝 %s", tcp.max_clients, client_addr)
                try:
                    client_conn.close()
                except OSError:
                    pass
                continue

            t = threading.Thread(
                target=self._handle_client,
                args=(client_conn, client_addr),
                daemon=True,
                name=f"TcpClient-{client_addr}",
            )
            t.start()

        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
        log.info("TCP 服务已停止")

    def stop(self) -> None:
        self._stop_event.set()
        self._close_all_clients()
        sock = self._server_sock
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def _register_client(self, conn: socket.socket) -> None:
        with self._lock:
            self._client_conns.append(conn)

    def _unregister_client(self, conn: socket.socket) -> None:
        with self._lock:
            try:
                self._client_conns.remove(conn)
            except ValueError:
                pass

    def _close_all_clients(self) -> None:
        with self._lock:
            conns = list(self._client_conns)
        for conn in conns:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass

    def _handle_client(self, conn: socket.socket, addr) -> None:
        log.info("客户端连接: %s", addr)
        self._register_client(conn)
        with self._lock:
            self._active_clients += 1
        self._notify_stats_throttled("")

        db: Optional[DbSession] = None
        try:
            try:
                db = create_session(self._cfg)
            except Exception as e:
                log.error("数据库连接失败（%s）: %s", addr, e)
                return

            self._read_loop(conn, addr, db)
        finally:
            self._unregister_client(conn)
            try:
                conn.close()
            except OSError:
                pass
            if db is not None:
                db.close()
            with self._lock:
                self._active_clients -= 1
            self._slots.release()
            self._notify_stats_throttled("")
            log.info("客户端断开: %s", addr)

    def _read_loop(self, conn: socket.socket, addr, db: DbSession) -> None:
        cfg = self._cfg
        enc = cfg.protocol.encoding
        timeout = cfg.tcp.keep_alive_seconds
        terminator = cfg.protocol.message_terminator
        max_bytes = cfg.protocol.max_message_bytes
        text_buf = ""

        while not self._stop_event.is_set():
            conn.settimeout(timeout)
            try:
                chunk = conn.recv(cfg.tcp.buffer_size)
            except socket.timeout:
                continue
            except OSError as e:
                if not self._stop_event.is_set():
                    log.warning("接收异常（%s）: %s", addr, e)
                break

            if not chunk:
                log.info("客户端主动断开: %s", addr)
                break

            try:
                text_buf += chunk.decode(enc)
            except UnicodeDecodeError as e:
                log.error("解码失败（%s）: %s", addr, e)
                break

            if len(text_buf.encode(enc)) > max_bytes:
                log.error("接收缓冲超限（%s），丢弃缓冲", addr)
                text_buf = ""
                continue

            if terminator:
                while terminator in text_buf:
                    line, text_buf = text_buf.split(terminator, 1)
                    line = line.strip()
                    if line:
                        self._process_line(line, addr, db)
            else:
                line = text_buf.strip()
                text_buf = ""
                if line:
                    self._process_line(line, addr, db)

    def _process_line(self, line: str, addr, db: DbSession) -> None:
        log.debug("收到数据（%s）: %s", addr, line[:120])
        try:
            record = parse_line(line, self._cfg)
            db.insert(record)
            self._notify_stats_throttled(record.get("barcode", ""))
        except Exception as e:
            log.error("处理数据失败（%s）: %s", addr, e)

    def _notify_stats_throttled(self, last_barcode: str) -> None:
        force = bool(last_barcode)
        if last_barcode:
            self._pending_barcode = last_barcode
        now = time.monotonic()
        if not force and now - self._last_stats_time < _STATS_INTERVAL_SEC:
            return
        self._last_stats_time = now
        barcode = self._pending_barcode
        if self._on_stats:
            with self._lock:
                cnt = self._active_clients
            try:
                self._on_stats(cnt, barcode)
            except Exception:
                pass

    @property
    def active_clients(self) -> int:
        with self._lock:
            return self._active_clients

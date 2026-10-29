"""主界面

布局：
  ┌──────────────────────────────────────┐
  │  状态区：服务灯 / Oracle灯 / 连接数    │
  │  最后条码：xxxxxxxx                    │
  ├──────────────────────────────────────┤
  │  [▶ 启动服务]   [■ 停止服务]  [⚙ 设置] │
  ├──────────────────────────────────────┤
  │  日志区（最近 200 行）                  │
  └──────────────────────────────────────┘
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from src.app.service import Service
from src.utils import logger as log_mod
from src.utils.logger import get_logger

log = get_logger(__name__)

_MAX_LOG_LINES = 200
# 界面日志批量刷新间隔（毫秒），避免高频写入时 Tk 卡顿
_GUI_LOG_FLUSH_MS = 150


class MainWindow:
    def __init__(self, root: tk.Tk):
        self._root = root
        self._root.title("FormassyBridge — TCP→Oracle 数据网关")
        self._root.resizable(True, True)
        self._root.minsize(680, 480)

        self._service: Optional[Service] = None
        self._closing = False
        self._log_pending: list[str] = []
        self._log_flush_scheduled = False
        self._build_ui()
        self._init_service()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = self._root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        # ── 状态区 ──────────────────────────────────────────────────
        status_frame = ttk.LabelFrame(root, text="运行状态", padding=8)
        status_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        status_frame.columnconfigure(3, weight=1)

        ttk.Label(status_frame, text="服务:").grid(row=0, column=0, sticky="w")
        self._lbl_svc = ttk.Label(status_frame, text="● 停止", foreground="gray")
        self._lbl_svc.grid(row=0, column=1, sticky="w", padx=(2, 20))

        ttk.Label(status_frame, text="当前连接:").grid(row=0, column=2, sticky="w")
        self._lbl_clients = ttk.Label(status_frame, text="0")
        self._lbl_clients.grid(row=0, column=3, sticky="w", padx=(2, 20))

        ttk.Label(status_frame, text="最后条码:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._lbl_barcode = ttk.Label(status_frame, text="—", foreground="#005599")
        self._lbl_barcode.grid(row=1, column=1, columnspan=3, sticky="w", pady=(4, 0))

        # ── 按钮区 ──────────────────────────────────────────────────
        btn_frame = ttk.Frame(root, padding=(10, 0))
        btn_frame.grid(row=1, column=0, sticky="ew", pady=4)

        self._btn_start = ttk.Button(btn_frame, text="▶ 启动服务", command=self._on_start, width=14)
        self._btn_start.pack(side="left", padx=(0, 6))

        self._btn_stop = ttk.Button(btn_frame, text="■ 停止服务", command=self._on_stop, width=14, state="disabled")
        self._btn_stop.pack(side="left", padx=(0, 6))

        ttk.Button(btn_frame, text="⚙ 设置", command=self._on_settings, width=10).pack(side="right")

        # ── 日志区 ──────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(root, text="运行日志", padding=6)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self._log_text = tk.Text(log_frame, state="disabled", wrap="none",
                                 font=("Consolas", 9), background="#1e1e1e", foreground="#d4d4d4",
                                 relief="flat", borderwidth=0)
        self._log_text.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._log_text.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(log_frame, orient="horizontal", command=self._log_text.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self._log_text.configure(xscrollcommand=hsb.set)

    # ------------------------------------------------------------------
    def _init_service(self) -> None:
        self._service = Service(
            on_status_change=self._on_status_change,
            on_stats=self._on_stats,
        )
        log_mod.set_gui_callback(self._append_log)

    # ------------------------------------------------------------------
    def _on_start(self) -> None:
        try:
            self._service.start()
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def _on_stop(self) -> None:
        if not self._service.is_running:
            return
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="disabled")
        self._lbl_svc.configure(text="● 正在停止…", foreground="orange")
        self._service.stop_async(on_done=lambda: self._root.after(0, self._finish_stop))

    def _finish_stop(self) -> None:
        if self._closing:
            return
        self._update_status(False, "")

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        log_mod.set_gui_callback(None)

        if self._service.is_running:
            self._root.title("FormassyBridge — 正在关闭…")
            self._btn_start.configure(state="disabled")
            self._btn_stop.configure(state="disabled")
            self._service.stop_async(on_done=lambda: self._root.after(0, self._root.destroy))
        else:
            self._root.destroy()

    def _ui_alive(self) -> bool:
        try:
            return bool(self._root.winfo_exists())
        except tk.TclError:
            return False

    def _on_settings(self) -> None:
        from src.app.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._root, self._service)
        self._root.wait_window(dlg.top)

    # ------------------------------------------------------------------
    def _on_status_change(self, running: bool, message: str) -> None:
        """从后台线程回调 → 通过 after 切回主线程更新 UI"""
        if self._closing:
            return
        self._root.after(0, self._update_status, running, message)

    def _update_status(self, running: bool, _message: str) -> None:
        if not self._ui_alive():
            return
        if running:
            self._lbl_svc.configure(text="● 运行中", foreground="green")
            self._btn_start.configure(state="disabled")
            self._btn_stop.configure(state="normal")
        else:
            self._lbl_svc.configure(text="● 停止", foreground="gray")
            self._btn_start.configure(state="normal")
            self._btn_stop.configure(state="disabled")
            self._lbl_clients.configure(text="0")

    def _on_stats(self, active_clients: int, last_barcode: str) -> None:
        if self._closing:
            return
        self._root.after(0, self._update_stats, active_clients, last_barcode)

    def _update_stats(self, active_clients: int, last_barcode: str) -> None:
        if not self._ui_alive():
            return
        self._lbl_clients.configure(text=str(active_clients))
        if last_barcode:
            self._lbl_barcode.configure(text=last_barcode)

    def _append_log(self, text: str) -> None:
        if self._closing:
            return
        self._log_pending.append(text)
        if not self._log_flush_scheduled:
            self._log_flush_scheduled = True
            self._root.after(_GUI_LOG_FLUSH_MS, self._flush_log_pending)

    def _flush_log_pending(self) -> None:
        self._log_flush_scheduled = False
        if self._closing or not self._log_pending or not self._ui_alive():
            self._log_pending.clear()
            return
        # 单次最多刷 30 行，其余留到下一轮，防止界面卡死
        batch = self._log_pending[:30]
        del self._log_pending[:30]
        text = "\n".join(batch)
        self._do_append_log(text)
        if self._log_pending:
            self._log_flush_scheduled = True
            self._root.after(_GUI_LOG_FLUSH_MS, self._flush_log_pending)

    def _do_append_log(self, text: str) -> None:
        if not self._ui_alive():
            return
        widget = self._log_text
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        lines = int(widget.index("end-1c").split(".")[0])
        if lines > _MAX_LOG_LINES:
            widget.delete("1.0", f"{lines - _MAX_LOG_LINES}.0")
        widget.configure(state="disabled")
        widget.see("end")

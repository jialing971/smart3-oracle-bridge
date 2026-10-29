"""管理员设置对话框

流程：
1. 弹出密码验证窗口（默认密码：admin）
2. 验证通过后显示设置表单（TCP + 数据库）
3. 可「测试 Oracle 连接」，确认后保存配置
4. 提示"需重启服务后生效"
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

import oracledb

from src.config.models import AppConfig, TcpConfig, DatabaseConfig
from src.utils.security import verify_password, hash_password
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.app.service import Service

log = get_logger(__name__)

_MAX_FAIL = 3


class SettingsDialog:
    def __init__(self, parent: tk.Tk, service: "Service"):
        self._service = service
        self._parent = parent
        self._fail_count = 0

        self.top = tk.Toplevel(parent)
        self.top.title("设置")
        self.top.resizable(False, False)
        self.top.grab_set()

        self._show_auth()

    # ------------------------------------------------------------------
    # 第一步：密码验证
    # ------------------------------------------------------------------
    def _show_auth(self) -> None:
        self._clear_top()
        frame = ttk.Frame(self.top, padding=20)
        frame.pack()

        ttk.Label(frame, text="请输入管理员密码", font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 10)
        )
        ttk.Label(frame, text="密码：").grid(row=1, column=0, sticky="e")
        self._pwd_var = tk.StringVar()
        pwd_entry = ttk.Entry(frame, textvariable=self._pwd_var, show="*", width=24)
        pwd_entry.grid(row=1, column=1, padx=(4, 0))
        pwd_entry.focus()
        pwd_entry.bind("<Return>", lambda _: self._verify_password())

        ttk.Button(frame, text="确认", command=self._verify_password, width=10).grid(
            row=2, column=0, columnspan=2, pady=(12, 0)
        )

    def _verify_password(self) -> None:
        pwd = self._pwd_var.get()
        stored = self._service.config.admin_password_hash
        if verify_password(pwd, stored):
            self._show_settings()
        else:
            self._fail_count += 1
            remaining = _MAX_FAIL - self._fail_count
            if remaining <= 0:
                messagebox.showerror("错误", "密码错误次数过多，已锁定", parent=self.top)
                self.top.destroy()
            else:
                messagebox.showwarning("错误", f"密码不正确，还有 {remaining} 次机会", parent=self.top)

    # ------------------------------------------------------------------
    # 第二步：设置表单
    # ------------------------------------------------------------------
    def _show_settings(self) -> None:
        self._clear_top()
        self.top.title("设置 — 管理员模式")

        nb = ttk.Notebook(self.top)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 4))

        # ── TCP ────────────────────────────────────────────────────
        tcp_tab = ttk.Frame(nb, padding=16)
        nb.add(tcp_tab, text="TCP 服务")
        self._tcp_vars = self._build_tcp_tab(tcp_tab)

        # ── 数据库 ──────────────────────────────────────────────────
        db_tab = ttk.Frame(nb, padding=16)
        nb.add(db_tab, text="Oracle 数据库")
        self._db_vars = self._build_db_tab(db_tab)

        # ── 修改密码 ────────────────────────────────────────────────
        pwd_tab = ttk.Frame(nb, padding=16)
        nb.add(pwd_tab, text="修改密码")
        self._build_pwd_tab(pwd_tab)

        # ── 底部按钮 ────────────────────────────────────────────────
        btn_frame = ttk.Frame(self.top, padding=(10, 0, 10, 10))
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="测试数据库连接", command=self._test_db).pack(side="left")
        ttk.Button(btn_frame, text="保存", command=self._save, width=10).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="取消", command=self.top.destroy, width=10).pack(side="right")

    def _build_tcp_tab(self, parent: ttk.Frame) -> dict:
        cfg = self._service.config.tcp
        vars_ = {}
        fields = [
            ("监听 IP（0.0.0.0 = 所有网卡）", "host", cfg.host),
            ("端口", "port", str(cfg.port)),
            ("接收缓冲区（字节）", "buffer_size", str(cfg.buffer_size)),
            ("保活超时（秒）", "keep_alive_seconds", str(cfg.keep_alive_seconds)),
            ("最大客户端数", "max_clients", str(cfg.max_clients)),
        ]
        for i, (label, key, val) in enumerate(fields):
            ttk.Label(parent, text=label + "：").grid(row=i, column=0, sticky="e", pady=3)
            v = tk.StringVar(value=val)
            ttk.Entry(parent, textvariable=v, width=28).grid(row=i, column=1, sticky="w", padx=(6, 0))
            vars_[key] = v
        return vars_

    def _build_db_tab(self, parent: ttk.Frame) -> dict:
        cfg = self._service.config.database
        vars_ = {}
        fields = [
            ("用户名", "user", cfg.user),
            ("密码", "password", cfg.password),
            ("DSN（IP:端口/服务名）", "dsn", cfg.dsn),
            ("Schema（表所在用户）", "schema", cfg.schema),
            ("表名", "table", cfg.table),
        ]
        for i, (label, key, val) in enumerate(fields):
            ttk.Label(parent, text=label + "：").grid(row=i, column=0, sticky="e", pady=3)
            v = tk.StringVar(value=val)
            show = "*" if key == "password" else ""
            ttk.Entry(parent, textvariable=v, width=36, show=show).grid(row=i, column=1, sticky="w", padx=(6, 0))
            vars_[key] = v
        return vars_

    def _build_pwd_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="新密码：").grid(row=0, column=0, sticky="e", pady=3)
        self._new_pwd = tk.StringVar()
        ttk.Entry(parent, textvariable=self._new_pwd, show="*", width=28).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(parent, text="确认新密码：").grid(row=1, column=0, sticky="e", pady=3)
        self._confirm_pwd = tk.StringVar()
        ttk.Entry(parent, textvariable=self._confirm_pwd, show="*", width=28).grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(parent, text="（留空则不修改密码）", foreground="gray").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    # ------------------------------------------------------------------
    def _test_db(self) -> None:
        user = self._db_vars["user"].get().strip()
        password = self._db_vars["password"].get().strip()
        dsn = self._db_vars["dsn"].get().strip()
        try:
            conn = oracledb.connect(user=user, password=password, dsn=dsn)
            conn.close()
            messagebox.showinfo("成功", "Oracle 数据库连接成功！", parent=self.top)
        except Exception as e:
            messagebox.showerror("失败", f"连接失败：\n{e}", parent=self.top)

    def _save(self) -> None:
        # 收集 TCP
        try:
            tcp = TcpConfig(
                host=self._tcp_vars["host"].get().strip(),
                port=int(self._tcp_vars["port"].get()),
                buffer_size=int(self._tcp_vars["buffer_size"].get()),
                keep_alive_seconds=int(self._tcp_vars["keep_alive_seconds"].get()),
                max_clients=int(self._tcp_vars["max_clients"].get()),
            )
        except ValueError as e:
            messagebox.showerror("输入错误", f"TCP 参数格式不正确：{e}", parent=self.top)
            return

        # 收集 DB
        db = DatabaseConfig(
            user=self._db_vars["user"].get().strip(),
            password=self._db_vars["password"].get().strip(),
            dsn=self._db_vars["dsn"].get().strip(),
            schema=self._db_vars["schema"].get().strip(),
            table=self._db_vars["table"].get().strip(),
        )

        # 密码修改
        new_pwd = self._new_pwd.get()
        confirm = self._confirm_pwd.get()
        old_hash = self._service.config.admin_password_hash
        if new_pwd:
            if new_pwd != confirm:
                messagebox.showerror("密码不一致", "两次输入的新密码不一致", parent=self.top)
                return
            new_hash = hash_password(new_pwd)
        else:
            new_hash = old_hash

        new_cfg = AppConfig(
            admin_password_hash=new_hash,
            tcp=tcp,
            database=db,
            protocol=self._service.config.protocol,
            field_mapping=self._service.config.field_mapping,
        )
        self._service.save_and_reload(new_cfg)

        msg = "配置已保存。"
        if self._service.is_running:
            msg += "\n\n请停止并重新启动服务以使新配置生效。"
        messagebox.showinfo("已保存", msg, parent=self.top)
        self.top.destroy()

    # ------------------------------------------------------------------
    def _clear_top(self) -> None:
        for w in self.top.winfo_children():
            w.destroy()

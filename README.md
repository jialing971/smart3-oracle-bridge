# SMART3 Oracle Bridge（程序名 FormassyBridge）

一个运行在 Windows 上的小型 TCP → Oracle 数据网关：接收 SMART3 以 TCP 客户端方式发来的逗号分隔文本，按配置解析字段，逐条写入 Oracle 数据库；提供 Tkinter 图形界面用于配置、启停和查看日志。

> **非官方项目**：本项目与 SMART3、Oracle 的厂商无隶属或授权关系，不代表官方立场，也不授权任何第三方商标。SMART3、Oracle 本体及第三方依赖不随本仓库提供。

## 功能概览

- TCP 服务端，支持多个并发客户端（`tcp.max_clients`）。
- 逗号分隔文本报文，字段顺序与目标列由 `field_mapping` 配置。
- 每条记录执行一次 `INSERT` 并立即 `commit`。
- Tkinter 图形界面：服务状态、当前连接数、最后条码、最近日志、TCP/数据库/管理密码设置。
- 数据库写入失败时记录日志，并对驱动异常做一次断线重连重试。
- 日志同时写入轮转文件（`logs/app.log`）和界面（最近 200 行）。

**不包含**：ACK/NACK 应答、TLS、客户端认证、持久化队列、失败补发、图片上传、自动建表、字段级校验规则。详见 [docs/limitations.md](docs/limitations.md)。

## 架构

```text
SMART3（TCP 客户端）
        │  逗号分隔文本
        ▼
src/tcp/server.py ──► src/protocol/parser.py
        │                     │
        ▼                     ▼
src/db/writer.py（oracledb Thin）──► Oracle 数据库
        ▲
src/app/service.py ──► src/app/gui/main_window.py（Tkinter）
src/config/loader.py、models.py        src/utils/logger.py、security.py
```

- `TcpServer` 在后台线程监听端口，每个客户端一个工作线程。
- 每个客户端线程持有独立的 `DbSession`，首次收到报文时才建立 Oracle 连接。
- `Service` 负责配置加载、服务启停和状态回调；GUI 只做展示与操作入口。

## 目录索引

| 路径 | 说明 |
| --- | --- |
| `main.py` | 程序入口，启动 Tkinter 窗口 |
| `src/app/gui/` | 主窗口与管理员设置对话框 |
| `src/app/service.py` | 配置加载、服务启停、状态回调 |
| `src/config/` | 配置数据类、加载/保存与校验 |
| `src/tcp/server.py` | TCP 监听、客户端线程、报文缓冲 |
| `src/protocol/parser.py` | 分隔符解析与必填字段检查 |
| `src/db/writer.py` | Oracle 连接、SQL 生成、写入与重试 |
| `src/utils/` | 日志、管理员密码哈希 |
| `config/default_config.json` | 脱敏默认配置模板（随仓库提供） |
| `docs/` | 协议、数据库、已知限制 |
| `examples/create_table.sql` | 手动建表示例 DDL（非自动执行） |
| `release/` | 打包产物的启动脚本与现场使用说明 |
| `build.bat` / `build.spec` | 可选的 PyInstaller 打包脚本 |
| `requirements.txt` | Python 依赖 |

## 环境要求

- Windows 10/11（图形界面基于 Tkinter）。
- Python 3.10 及以上（官方 Windows 安装包通常自带 Tkinter；可用 `python -m tkinter` 自检）。
- 能访问目标 Oracle 数据库的网络。
- 使用 python-oracledb **Thin 模式**，不需要安装 Oracle Client。官方文档写明支持 Oracle Database 12.1 及以上；具体兼容性与安全认证配置需按你的数据库版本验证，本项目未实现 Thick 模式，也不声称支持 11g。

## 快速开始（源码运行）

```bat
git clone https://github.com/jialing971/smart3-oracle-bridge.git
cd smart3-oracle-bridge
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

首次运行行为：

1. 程序在 `config/` 下发现没有 `config.json` 时，会复制 `default_config.json` 生成 `config.json`。
2. 模板中的数据库地址是 `oracle.example.invalid`、口令为空，仅用于占位。
3. 界面启动本身**不会连接数据库**；数据库连接在收到第一条报文（首次写入）时才建立。
4. 通过“设置”填写真实数据库信息；跨机器连接时，将监听地址改为本机产线网卡地址或 `0.0.0.0`，并限制防火墙来源。保存后启动服务。

以后只需修改 `config/config.json`；修改配置后需要停止并重新启动服务才会生效（TCP 与数据库设置也可在界面中修改）。

## 配置说明

运行配置：`config/config.json`（本地文件，已被 `.gitignore` 忽略，不应提交或随发布包分发）。

默认模板：`config/default_config.json`（脱敏，随仓库提供）。不要直接把现场真实配置写回模板。

| 配置项 | 说明 |
| --- | --- |
| `admin_password_hash` | 管理员密码的 SHA-256 十六进制值；默认密码为 `admin` |
| `tcp.host` | 监听地址；`127.0.0.1` 仅本机，`0.0.0.0` 监听所有网卡 |
| `tcp.port` | 监听端口，默认 `1024` |
| `tcp.buffer_size` | 单次 `recv` 缓冲区字节数 |
| `tcp.keep_alive_seconds` | `recv` 超时秒数；超时后继续等待，**不是**空闲断开 |
| `tcp.max_clients` | 最大并发客户端数，超出时新连接会被关闭 |
| `database.user` / `password` / `dsn` / `schema` / `table` | Oracle 连接与目标表；DSN 形如 `host:port/service_name` |
| `protocol.separator` | 分隔符，默认逗号 |
| `protocol.encoding` | 报文编码，默认 `utf-8` |
| `protocol.message_terminator` | 报文结束符；空字符串表示“一次 `recv` 即一条”，见协议文档 |
| `protocol.max_message_bytes` | 单条/缓冲报文最大字节数 |
| `field_mapping` | 字段位置、目标列名、是否必填 |

`protocol` 与 `field_mapping` **只能手工编辑 JSON**；界面设置只覆盖 TCP、数据库和管理员密码。`field_mapping` 中 `column` 必须是目标表已存在的列名。

示例（默认模板的字段顺序）：

```text
index 0 -> barcode        必填
index 1 -> image_path     可选
index 2 -> result_code    可选
index 3 -> employee_id    可选
index 4 -> station_id     可选
index 5 -> event_date_str 可选
index 6 -> event_time_str 可选
```

## 使用流程

1. 启动程序，打开“设置”，输入管理员密码（默认 `admin`），填写 TCP 与 Oracle 参数。
2. 可点击“测试数据库连接”手动验证账号与 DSN；该按钮只建立并关闭一次连接，不会自动执行任何 SQL，也不会写入数据。
3. 保存配置，回到主界面点击“启动服务”。
4. 让 SMART3 作为 TCP 客户端连接到本机监听地址和端口，并按约定发送报文。
5. 在主界面查看连接数、最后条码与日志；日志文件位于 `logs/app.log`。
6. 现场停机时先点击“停止服务”，再关闭窗口。

## 安全说明

- 默认管理员密码是 `admin`，仅用于阻止误操作，**不是**强访问控制。密码使用不加盐的 SHA-256 保存；登录失败 3 次会关闭当前设置窗口，但重新打开可再次尝试。
- 数据库口令以**明文**保存在本地 `config/config.json` 中；程序不支持从环境变量读取口令。请通过文件系统权限保护该文件，不要提交到 Git、不要随发布包分发。
- 程序不提供 TLS、客户端证书或来源 IP 认证。监听 `0.0.0.0` 时，任何能访问该端口的客户端都可以发送数据；请用防火墙/网络隔离限制来源。
- 日志可能包含条码、错误详情等业务信息，请同样按敏感文件管理。
- 发布或交付前请检查打包目录，确认不包含 `config/config.json` 和 `logs/`。

## 打包（可选，未在本次发布中验证）

`build.bat` 会通过 `pip` 安装/更新 `requirements.txt` 中的依赖和 PyInstaller，然后按 `build.spec` 生成 `dist/FormassyBridge/` 与发布 ZIP。该脚本会修改当前 Python 环境，属于用户手动可选操作。

本次源码发布**没有**验证打包产物；本次使用的内置 Python 运行时导入 PyInstaller 时缺少可用的 `pywin32-ctypes`，不能据此声称 EXE 已通过测试。公开版脚本不复制运行配置，并在压缩前检查目标目录是否残留 `config/config.json` 或 `logs/`；发现时中止，不删除这些文件。打包后仍需检查 `dist`，确认模板未被填入真实凭据，且不含其他敏感文件。发布目录的使用说明与启动脚本见 `release/`。

## 文档

- [协议说明](docs/protocol.md)
- [数据库配置](docs/database.md)
- [已知限制与验证边界](docs/limitations.md)
- [建表示例](examples/create_table.sql)

## 许可证

MIT License，Copyright (c) 2026 jialing971，详见 [LICENSE](LICENSE)。

第三方依赖（如 python-oracledb、cryptography、PyInstaller）不随本仓库提供，其许可证与使用条件以各自项目为准。

# 数据库配置

## 驱动与连接方式

- 使用 [python-oracledb](https://python-oracledb.readthedocs.io/) 的 **Thin 模式**（`oracledb.connect(...)` 的默认模式）。
- Thin 模式不需要安装 Oracle Client 或 Instant Client。
- 本程序没有调用 `oracledb.init_oracle_client()`，不包含 Thick 模式初始化。
- 官方文档写明 Thin 模式支持 Oracle Database 12.1 及以上：
  <https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html#supported-oracle-database-versions>
- 具体数据库版本、认证方式、加密/安全配置需要结合现场环境验证；本程序**不宣称支持 Oracle 11g**。

## 配置项

`config/config.json` 中的 `database` 段：

```json
"database": {
  "user": "BRIDGE_USER",
  "password": "",
  "dsn": "oracle.example.invalid:1521/EXAMPLEPDB",
  "schema": "BRIDGE_USER",
  "table": "SMART3_RESULTS"
}
```

| 字段 | 说明 |
| --- | --- |
| `user` | 连接数据库的账号 |
| `password` | 账号口令，**明文保存在本地配置文件** |
| `dsn` | 连接串，示例格式 `host:port/service_name`（EZ Connect） |
| `schema` | 目标表所在 schema；会转为大写并做标识符校验 |
| `table` | 目标表名；会转为大写并做标识符校验 |

注意：

- 程序不做环境变量读取；口令只能写在 `config.json` 或通过界面输入后保存。
- `schema`、`table`、列名只允许 `A-Za-z_` 开头，后接字母、数字、`_`、`$`、`#`，最长 128 字符；程序会转为大写。使用带引号的大小写敏感对象名不受支持。
- `field_mapping` 的 `column` 必须与目标表已有列名一致；程序不会自动建表，也不会校验表结构。

## 生成的 SQL

程序启动客户端会话后，根据 `field_mapping` 生成参数化 INSERT：

```sql
INSERT INTO BRIDGE_USER.SMART3_RESULTS (BARCODE, IMAGE_PATH, RESULT_CODE, EMPLOYEE_ID, STATION_ID, EVENT_DATE_STR, EVENT_TIME_STR)
VALUES (:1, :2, :3, :4, :5, :6, :7)
```

值通过绑定变量传入，不拼接进 SQL 文本。每条 INSERT 后立即 `commit`，没有批量提交或事务分组。

## 权限建议

配置账号需要：

- `CREATE SESSION`（登录数据库）；
- 对目标表的 `INSERT` 权限。

如果目标表由该账号自己创建并拥有，则拥有者默认具备相应权限；如果使用独立采集账号写入其他 schema 的表，需要由 DBA 手动授予最小 INSERT 权限。本仓库**不提供**创建账号、授权或真实业务表的脚本。

`examples/create_table.sql` 只是与默认字段映射一致的手动建表示例，不会被执行，也不代表生产表结构。

## 字段类型

示例 DDL 中所有列都使用 `VARCHAR2`，日期和时间以字符串保存，程序不做日期/时间转换或校验：

- `event_date_str` 原样写入，例如 `2026-10-29`；
- `event_time_str` 原样写入，例如 `08:30:00`。

如果现场表使用 `DATE`、`TIMESTAMP` 或 `NUMBER` 等类型，需要自行确认驱动转换和 NLS 设置；本程序没有针对这些类型做专门处理或测试。

长度仅为示例，请根据实际条码、路径和业务字段长度调整；程序本身不做长度截断。

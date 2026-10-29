"""配置数据模型（纯数据类，不依赖任何其他内部模块）"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class TcpConfig:
    host: str = "0.0.0.0"
    port: int = 1024
    buffer_size: int = 4096
    keep_alive_seconds: int = 10
    max_clients: int = 5


@dataclass
class DatabaseConfig:
    user: str = ""
    password: str = ""
    dsn: str = ""          # host:port/service_name
    schema: str = ""
    table: str = ""


@dataclass
class ProtocolConfig:
    separator: str = ","
    encoding: str = "utf-8"
    # 报文结束符；空字符串表示「一次 recv 即一条」（兼容原 Smart3）
    message_terminator: str = ""
    # 单条报文最大字节，防止异常数据撑爆内存
    max_message_bytes: int = 65536


@dataclass
class FieldMapping:
    index: int = 0
    column: str = ""
    required: bool = False


@dataclass
class AppConfig:
    admin_password_hash: str = ""
    tcp: TcpConfig = field(default_factory=TcpConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    protocol: ProtocolConfig = field(default_factory=ProtocolConfig)
    field_mapping: List[FieldMapping] = field(default_factory=list)

"""TCP 数据包解析"""
from typing import Dict

from src.config.models import AppConfig
from src.utils.logger import get_logger

log = get_logger(__name__)


def parse_line(raw: str, cfg: AppConfig) -> Dict[str, str]:
    max_len = cfg.protocol.max_message_bytes
    if len(raw.encode(cfg.protocol.encoding, errors="replace")) > max_len:
        raise ValueError(f"报文超过最大长度 {max_len} 字节")

    sep = cfg.protocol.separator
    parts = [p.strip() for p in raw.split(sep)]

    result: Dict[str, str] = {}
    for mapping in cfg.field_mapping:
        idx = mapping.index
        value = parts[idx] if idx < len(parts) else ""
        if mapping.required and not value:
            raise ValueError(
                f"必填字段 [{mapping.column}]（index={idx}）为空，原始数据：{raw!r}"
            )
        result[mapping.column] = value

    log.debug("解析结果: barcode=%s", result.get("barcode", ""))
    return result

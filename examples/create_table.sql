-- SMART3 Oracle Bridge 手动建表示例
-- 仅用于说明默认 field_mapping 对应的列结构，不会被程序自动执行。
-- schema / 账号 / 权限 / 真实业务表请由 DBA 根据现场规范另行创建。
-- 所有字段均为 VARCHAR2；长度只是示例，请按实际业务评估后调整。

CREATE TABLE BRIDGE_USER.SMART3_RESULTS (
    BARCODE        VARCHAR2(128) NOT NULL,
    IMAGE_PATH     VARCHAR2(512),
    RESULT_CODE    VARCHAR2(32),
    EMPLOYEE_ID    VARCHAR2(64),
    STATION_ID     VARCHAR2(64),
    EVENT_DATE_STR VARCHAR2(10),
    EVENT_TIME_STR VARCHAR2(16)
);

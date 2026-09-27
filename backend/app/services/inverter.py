"""逆变器管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import csv
import io
import re
from typing import Any

from app.store import store

MODULE = "inverter"
REQUIRED_FIELDS = ["逆变器编号", "逆变器型号", "额定功率"]
STATUS_ORDER = ["运行", "待机", "告警", "停机", "维修中"]
ACTION_RULES = {"停机检查": "停机", "复位告警": "待机", "恢复运行": "运行"}
NEGATIVE_ACTIONS = []

# 表格文件通道：模板列、功率写法与待修正判定都收在这一处，导入导出共用。
SHEET_COLUMNS = ["逆变器编号", "逆变器型号", "额定功率", "所属电站"]
POWER_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:kW|千瓦)?$", re.IGNORECASE)


def normalize_power(raw: str) -> str | None:
    """把「250」「250kW」「250千瓦」归一成 250kW；认不出的写法返回 None。"""
    match = POWER_PATTERN.match(raw.strip())
    if not match:
        return None
    number = match.group(1)
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    if float(number) <= 0:
        return None
    return f"{number}kW"


def render_sheet(rows: list[dict[str, Any]]) -> str:
    """把行集合渲染成带 BOM 的 CSV 文本，Excel/WPS 打开中文不乱码。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(SHEET_COLUMNS)
    for row in rows:
        writer.writerow([str(row.get(column) or "") for column in SHEET_COLUMNS])
    return "\ufeff" + buffer.getvalue()


class InverterService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("逆变器编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"逆变器 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于逆变器管理可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"逆变器已{action}"

    def build_sheet_template(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        plant: str | None = None,
    ) -> tuple[str, int]:
        """按设备范围生成台账模板：范围内的逆变器预填进去，空范围也只给表头。"""
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("逆变器编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if plant:
            rows = [row for row in rows if plant in str(row.get("所属电站", ""))]
        return render_sheet(rows), len(rows)

    def parse_sheet(self, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        """解析填好的表格：返回（可接收行、待修正清单、不可识别行数）。

        四列都填了的行才算可识别；编号重复或功率写法认不出的行进待修正清单，
        其余不可识别的行直接不计入。
        """
        reader = csv.reader(io.StringIO(content.lstrip("\ufeff")))
        rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not rows:
            raise ValueError("表格是空的，请按模板填入逆变器编号、型号、额定功率和所属电站")
        header = [cell.strip().lstrip("\ufeff") for cell in rows[0]]
        missing = [column for column in SHEET_COLUMNS if column not in header]
        if missing:
            raise ValueError(f"表头无法识别，缺少必要列：{'、'.join(missing)}")
        position = {column: header.index(column) for column in SHEET_COLUMNS}

        accepted: list[dict[str, Any]] = []
        corrections: list[dict[str, Any]] = []
        discarded = 0
        seen_codes = {str(row.get("逆变器编号", "")) for row in store.rows(MODULE)}
        for line_no, row in enumerate(rows[1:], start=2):
            values = {
                column: (row[position[column]].strip() if position[column] < len(row) else "")
                for column in SHEET_COLUMNS
            }
            if any(not values[column] for column in SHEET_COLUMNS):
                discarded += 1
                continue
            reasons = []
            if values["逆变器编号"] in seen_codes:
                reasons.append("逆变器编号重复")
            power = normalize_power(values["额定功率"])
            if power is None:
                reasons.append("额定功率格式不符")
            if reasons:
                corrections.append({"line": line_no, "values": values, "reasons": reasons})
                continue
            seen_codes.add(values["逆变器编号"])
            values["额定功率"] = power
            accepted.append(values)
        return accepted, corrections, discarded

    def commit_sheet_rows(
        self, rows: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """确认导入：提交前再按当前台账复核一遍，通过的登记入库，其余说明原因。"""
        created: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for row in rows:
            values = {column: str(row.get(column) or "").strip() for column in SHEET_COLUMNS}
            if any(not values[column] for column in SHEET_COLUMNS):
                skipped.append({"values": values, "reasons": ["字段不完整，不可识别"]})
                continue
            reasons = []
            if any(str(existing.get("逆变器编号", "")) == values["逆变器编号"] for existing in store.rows(MODULE)):
                reasons.append("逆变器编号重复")
            power = normalize_power(values["额定功率"])
            if power is None:
                reasons.append("额定功率格式不符")
            if reasons:
                skipped.append({"values": values, "reasons": reasons})
                continue
            values["额定功率"] = power
            entry, _ = self.create_entry(values)
            entry["所属电站"] = values["所属电站"]
            created.append(entry)
        return created, skipped

    def build_sheet_export(self, rows: list[dict[str, Any]]) -> str:
        """把确认后的结果打包成新的表格文件，列口径与模板一致，可带回现场再次使用。"""
        return render_sheet(rows)

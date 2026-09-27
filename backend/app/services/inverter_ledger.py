"""逆变器台账表格文件通道：模板生成、导入解析、待修正清单与确认打包。

表格文件统一用 CSV（Excel/WPS 都能直接打开），只依赖标准库；
上传内容带 UTF-8 BOM 也能识别，导出的文件同样带 BOM，现场用 Excel 打开中文不乱码。
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any

from app.store import store

MODULE = "inverter"
PLANT_MODULE = "plant"
LEDGER_HEADERS = ["逆变器编号", "逆变器型号", "额定功率", "所属电站"]
# 额定功率只认数字，可带 kW/千瓦 单位后缀，例如 250、250.5、250kW、250 千瓦
POWER_PATTERN = re.compile(r"^\d+(\.\d+)?\s*(kW|KW|kw|千瓦)?$")


class InverterLedgerService:
    """一次导入就是一个批次：先解析出可接收行与待修正行，确认后才真正入账。"""

    def __init__(self) -> None:
        self._batches: dict[str, dict[str, Any]] = {}
        self._batch_seq = 0

    def scope_options(self) -> list[str]:
        """设备范围选项：取自电站档案里的电站名称，去重后保持原有顺序。"""
        names: list[str] = []
        for row in store.rows(PLANT_MODULE):
            name = str(row.get("电站名称") or "").strip()
            if name and name not in names:
                names.append(name)
        return names

    def build_template(self, plants: list[str]) -> str:
        """按设备范围生成台账模板：范围内已有逆变器预填进去，空范围也只给表头。"""
        rows = store.rows(MODULE)
        if plants:
            rows = [row for row in rows if str(row.get("所属电站") or "").strip() in plants]
        body = [[str(row.get(head) or "") for head in LEDGER_HEADERS] for row in rows]
        return self._to_csv(body)

    def create_import(self, filename: str, content: str) -> dict[str, Any]:
        """解析上传的表格文本，返回批次号、可接收行与待修正清单。"""
        accepted, pending, error = self._parse(content)
        if error:
            return {"ok": False, "message": error}
        self._batch_seq += 1
        batch_id = f"LEDGER-{self._batch_seq:04d}"
        self._batches[batch_id] = {
            "filename": filename,
            "accepted": accepted,
            "pending": pending,
            "confirmed": False,
            "confirmed_rows": [],
        }
        return {
            "ok": True,
            "message": f"解析完成：可接收 {len(accepted)} 行，待修正 {len(pending)} 行",
            "batch_id": batch_id,
            "accepted": accepted,
            "pending": pending,
        }

    def confirm_batch(self, batch_id: str) -> tuple[list[dict[str, Any]] | None, str]:
        """把批次里已接收的行写入逆变器台账；确认过的批次不允许重复入账。"""
        batch = self._batches.get(batch_id)
        if batch is None:
            return None, f"导入批次 {batch_id} 不存在或已过期，请重新上传"
        if batch["confirmed"]:
            return None, f"批次 {batch_id} 已确认入库，请勿重复提交"
        rows = store.rows(MODULE)
        next_id = max((int(row.get("id", 0)) for row in rows), default=0)
        existing = {str(row.get("逆变器编号") or "").strip() for row in rows}
        committed: list[dict[str, Any]] = []
        skipped = 0
        for item in batch["accepted"]:
            code = item["逆变器编号"]
            if code in existing:
                # 确认之前台账可能已被别的入口写入同编号，兜底防重
                skipped += 1
                continue
            next_id += 1
            entry: dict[str, Any] = {"id": next_id}
            entry.update({head: item[head] for head in LEDGER_HEADERS})
            entry["status"] = "运行"
            entry["pending"] = True
            entry["abnormal"] = False
            rows.append(entry)
            existing.add(code)
            committed.append(entry)
        batch["confirmed"] = True
        batch["confirmed_rows"] = committed
        message = f"批次 {batch_id} 已确认入库 {len(committed)} 条"
        if skipped:
            message += f"，{skipped} 条因编号与台账冲突被拦下"
        return committed, message

    def build_export(self, batch_id: str) -> tuple[str | None, str | None]:
        """把已确认的批次打包成新的表格文件，供运维人员带回现场。"""
        batch = self._batches.get(batch_id)
        if batch is None:
            return None, f"导入批次 {batch_id} 不存在或已过期"
        if not batch["confirmed"]:
            return None, f"批次 {batch_id} 尚未确认入库，请先确认再打包下载"
        body = [[str(row.get(head) or "") for head in LEDGER_HEADERS] for row in batch["confirmed_rows"]]
        return self._to_csv(body), None

    def _parse(self, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
        """逐行校验：只接收可识别的行，重复编号与功率格式不符的行进待修正清单。"""
        text = content.lstrip("\ufeff")
        if text.startswith("PK"):
            return [], [], "检测到 Excel 工作簿，请先另存为 CSV（逗号分隔）文件再上传"
        reader = csv.reader(io.StringIO(text))
        raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not raw_rows:
            return [], [], "文件内容为空，请下载模板填写后再上传"
        header = [cell.strip() for cell in raw_rows[0]]
        index: dict[str, int] = {}
        for name in LEDGER_HEADERS:
            if name not in header:
                return [], [], f"表头缺少「{name}」列，请核对是否使用了最新模板"
            index[name] = header.index(name)
        existing = {str(row.get("逆变器编号") or "").strip() for row in store.rows(MODULE)}
        seen: set[str] = set()
        accepted: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        for line_no, raw in enumerate(raw_rows[1:], start=2):
            values = {
                name: (raw[idx].strip() if idx < len(raw) else "")
                for name, idx in index.items()
            }
            reasons: list[str] = []
            missing = [name for name in LEDGER_HEADERS if not values[name]]
            if missing:
                reasons.append(f"缺少必填字段：{'、'.join(missing)}")
            code = values["逆变器编号"]
            if code:
                if code in seen or code in existing:
                    reasons.append("逆变器编号重复")
                seen.add(code)
            power = values["额定功率"]
            if power and not POWER_PATTERN.match(power):
                reasons.append("额定功率格式不符（应为数字，可带 kW/千瓦 单位）")
            if reasons:
                pending.append({"line": line_no, "values": values, "reasons": reasons})
            else:
                accepted.append(values)
        return accepted, pending, None

    def _to_csv(self, body: list[list[str]]) -> str:
        """表头 + 数据行，开头补 BOM，保证 Excel 直接打开不乱码。"""
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(LEDGER_HEADERS)
        writer.writerows(body)
        return "\ufeff" + buffer.getvalue()

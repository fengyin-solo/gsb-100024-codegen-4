"""逆变器管理接口：维护逆变器，覆盖停机检查、复位告警、恢复运行等动作。

另挂台账表格文件通道：/ledger/template 下载模板、/ledger/import 解析上传、
/ledger/confirm 确认入账、/ledger/export 打包确认结果。
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Response

from app.schemas import (
    ActionResult,
    EntryPayload,
    LedgerConfirmPayload,
    LedgerImportPayload,
    LedgerImportResult,
    PageResult,
)
from app.services.inverter import InverterService
from app.services.inverter_ledger import InverterLedgerService

router = APIRouter(prefix="/api/inverter", tags=["逆变器管理"])

service = InverterService()
ledger_service = InverterLedgerService()

LIST_FIELDS = ["逆变器编号", "逆变器型号", "额定功率", "所属电站", "投产日期", "运行时长", "告警次数", "运行状态"]
STATUSES = ["运行", "待机", "告警", "停机", "维修中"]


def _csv_response(content: str, filename: str) -> Response:
    """表格文件下载响应：中文文件名按 RFC 5987 编码，避免浏览器拿到乱码名。"""
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"},
    )


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按逆变器编号检索"),
    status: str | None = Query(default=None, description="运行、待机、告警、停机、维修中"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按逆变器编号与状态过滤逆变器管理列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出逆变器管理清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "inverter", "total": total, "items": items}


@router.get("/ledger/scope")
def ledger_scope() -> dict[str, Any]:
    """设备范围选项：返回电站档案里的电站名称，供下载模板前勾选。"""
    return {"plants": ledger_service.scope_options()}


@router.get("/ledger/template")
def download_template(
    plants: list[str] = Query(default=[], description="设备范围：按所属电站过滤，空为全部"),
) -> Response:
    """按设备范围下载台账模板；范围内没有逆变器时仍返回带表头的空模板。"""
    content = ledger_service.build_template(plants)
    return _csv_response(content, "逆变器台账模板.csv")


@router.post("/ledger/import", response_model=LedgerImportResult)
def import_ledger(payload: LedgerImportPayload) -> LedgerImportResult:
    """解析上传的表格文本：只接收可识别的行，问题行连同原因进入待修正清单。"""
    if not payload.content.strip():
        return LedgerImportResult(ok=False, message="上传内容为空，请先下载模板填写后再导入")
    result = ledger_service.create_import(payload.filename, payload.content)
    return LedgerImportResult(**result)


@router.post("/ledger/confirm", response_model=ActionResult)
def confirm_ledger(payload: LedgerConfirmPayload) -> ActionResult:
    """确认入库：把批次里已接收的行写入台账，已确认的批次不能重复提交。"""
    if not payload.batch_id.strip():
        return ActionResult(ok=False, message="缺少导入批次号，请先上传解析")
    entries, message = ledger_service.confirm_batch(payload.batch_id)
    if entries is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry={"count": len(entries)})


@router.get("/ledger/export")
def export_ledger(batch_id: str = Query(description="已确认的导入批次号")) -> Response:
    """把已确认批次的入账结果打包成新的表格文件，供带回现场核对。"""
    content, error = ledger_service.build_export(batch_id)
    if error:
        raise HTTPException(status_code=404, detail=error)
    assert content is not None
    return _csv_response(content, f"逆变器台账确认结果_{batch_id}.csv")


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条逆变器明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"逆变器 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条逆变器，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="逆变器已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条逆变器执行停机检查、复位告警、恢复运行；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

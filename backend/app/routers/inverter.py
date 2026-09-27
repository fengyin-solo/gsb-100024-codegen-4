"""逆变器管理接口：维护逆变器，覆盖停机检查、复位告警、恢复运行等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response

from app.schemas import ActionResult, EntryPayload, PageResult, SheetPreviewPayload, SheetRowsPayload
from app.services.inverter import InverterService

router = APIRouter(prefix="/api/inverter", tags=["逆变器管理"])

service = InverterService()

LIST_FIELDS = ["逆变器编号", "逆变器型号", "额定功率", "所属电站", "投产日期", "运行时长", "告警次数", "运行状态"]
STATUSES = ["运行", "待机", "告警", "停机", "维修中"]

CSV_MEDIA_TYPE = "text/csv; charset=utf-8"


def csv_response(content: str, filename: str) -> Response:
    """打包成表格文件下载；文件名用 ASCII，中文名由前端下载时指定。"""
    return Response(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# 注意：/export 与 /sheet/* 必须放在 /{entry_id} 之前，否则会被当成 entry_id 抢走。


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出逆变器管理清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "inverter", "total": total, "items": items}


@router.get("/sheet/template")
def sheet_template(
    keyword: str | None = Query(default=None, description="按逆变器编号圈定范围"),
    status: str | None = Query(default=None, description="运行、待机、告警、停机、维修中"),
    plant: str | None = Query(default=None, description="按所属电站圈定范围"),
) -> Response:
    """按设备范围生成台账模板：范围内的逆变器预填进模板，空范围也只给表头。"""
    content, _ = service.build_sheet_template(keyword=keyword, status=status, plant=plant)
    return csv_response(content, "inverter_sheet_template.csv")


@router.post("/sheet/preview")
def sheet_preview(payload: SheetPreviewPayload) -> dict[str, Any]:
    """解析填好的表格：只接收可识别的行，重复编号与功率格式不符的行进入待修正清单。"""
    try:
        accepted, corrections, discarded = service.parse_sheet(payload.content)
    except ValueError as exc:
        return {"ok": False, "message": str(exc), "accepted": [], "corrections": [], "discarded": 0}
    return {
        "ok": True,
        "message": f"可接收 {len(accepted)} 行，待修正 {len(corrections)} 行，不可识别 {discarded} 行已忽略",
        "accepted": accepted,
        "corrections": corrections,
        "discarded": discarded,
    }


@router.post("/sheet/commit")
def sheet_commit(payload: SheetRowsPayload) -> dict[str, Any]:
    """确认导入：把可接收的行登记进台账，入库前再复核一遍。"""
    if not payload.rows:
        return {"ok": False, "message": "没有可导入的行，请先在模板上填写并上传", "created": [], "skipped": []}
    created, skipped = service.commit_sheet_rows(payload.rows)
    return {
        "ok": bool(created),
        "message": f"已登记 {len(created)} 台逆变器，{len(skipped)} 行未通过复核",
        "created": created,
        "skipped": skipped,
    }


@router.post("/sheet/export")
def sheet_export(payload: SheetRowsPayload) -> Response:
    """把确认后的结果打包成新的表格文件，可带回现场；空结果也给带表头的文件。"""
    return csv_response(service.build_sheet_export(payload.rows), "inverter_sheet_confirmed.csv")


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

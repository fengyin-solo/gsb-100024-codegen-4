"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class LedgerImportPayload(BaseModel):
    """表格文件通道上传内容：前端读出文件文本后随文件名一起提交。"""

    filename: str = ""
    content: str = ""


class LedgerConfirmPayload(BaseModel):
    """确认入库时只需带回导入批次号。"""

    batch_id: str = ""


class LedgerImportResult(BaseModel):
    """导入解析结果：可接收行直接确认，问题行进入待修正清单。"""

    ok: bool
    message: str
    batch_id: str | None = None
    accepted: list[dict[str, Any]] = Field(default_factory=list)
    pending: list[dict[str, Any]] = Field(default_factory=list)



class PlantEntry(BaseModel):
    """光伏电站明细结构。"""

    field_0: str | None = None  # 电站编号
    field_1: str | None = None  # 电站名称
    field_2: str | None = None  # 装机容量
    field_3: str | None = None  # 并网日期
    field_4: str | None = None  # 所属区域
    field_5: str | None = None  # 运维负责人
    field_6: str | None = None  # 组件厂家
    field_7: str | None = None  # 电站状态

class InspectionEntry(BaseModel):
    """巡检任务明细结构。"""

    field_0: str | None = None  # 巡检编号
    field_1: str | None = None  # 巡检站点
    field_2: str | None = None  # 巡检类型
    field_3: str | None = None  # 计划日期
    field_4: str | None = None  # 巡检人员
    field_5: str | None = None  # 巡检路线
    field_6: str | None = None  # 发现缺陷数
    field_7: str | None = None  # 巡检状态

class PanelCleanEntry(BaseModel):
    """清洗任务明细结构。"""

    field_0: str | None = None  # 清洗编号
    field_1: str | None = None  # 清洗区域
    field_2: str | None = None  # 组件数量
    field_3: str | None = None  # 清洗方式
    field_4: str | None = None  # 清洗日期
    field_5: str | None = None  # 清洗班组
    field_6: str | None = None  # 清洗效果
    field_7: str | None = None  # 清洗状态

class InverterEntry(BaseModel):
    """逆变器明细结构。"""

    field_0: str | None = None  # 逆变器编号
    field_1: str | None = None  # 逆变器型号
    field_2: str | None = None  # 额定功率
    field_3: str | None = None  # 所属电站
    field_4: str | None = None  # 投产日期
    field_5: str | None = None  # 运行时长
    field_6: str | None = None  # 告警次数
    field_7: str | None = None  # 运行状态

class PowerDataEntry(BaseModel):
    """发电记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 电站编号
    field_2: str | None = None  # 发电量
    field_3: str | None = None  # 辐照度
    field_4: str | None = None  # 组件温度
    field_5: str | None = None  # 环境温度
    field_6: str | None = None  # 记录时间
    field_7: str | None = None  # 数据状态

class FaultEntry(BaseModel):
    """故障记录明细结构。"""

    field_0: str | None = None  # 故障编号
    field_1: str | None = None  # 故障设备
    field_2: str | None = None  # 故障现象
    field_3: str | None = None  # 发现人员
    field_4: str | None = None  # 发现时间
    field_5: str | None = None  # 严重等级
    field_6: str | None = None  # 处置措施
    field_7: str | None = None  # 故障状态

class SparePartEntry(BaseModel):
    """备品备件明细结构。"""

    field_0: str | None = None  # 备件编号
    field_1: str | None = None  # 备件名称
    field_2: str | None = None  # 适用设备
    field_3: str | None = None  # 规格型号
    field_4: str | None = None  # 存放位置
    field_5: str | None = None  # 最低储备
    field_6: str | None = None  # 当前数量
    field_7: str | None = None  # 备件状态

class TransformerEntry(BaseModel):
    """箱式变压器明细结构。"""

    field_0: str | None = None  # 箱变编号
    field_1: str | None = None  # 箱变型号
    field_2: str | None = None  # 额定容量
    field_3: str | None = None  # 所属电站
    field_4: str | None = None  # 油温
    field_5: str | None = None  # 绕组温度
    field_6: str | None = None  # 上次检修日
    field_7: str | None = None  # 箱变状态

class SwitchgearEntry(BaseModel):
    """开关设备明细结构。"""

    field_0: str | None = None  # 设备编号
    field_1: str | None = None  # 设备名称
    field_2: str | None = None  # 电压等级
    field_3: str | None = None  # 所属电站
    field_4: str | None = None  # 分合状态
    field_5: str | None = None  # 操作许可
    field_6: str | None = None  # 上次操作日
    field_7: str | None = None  # 设备状态

class MeterEntry(BaseModel):
    """计量表计明细结构。"""

    field_0: str | None = None  # 表计编号
    field_1: str | None = None  # 表计型号
    field_2: str | None = None  # 计量点位置
    field_3: str | None = None  # 倍率
    field_4: str | None = None  # 上次示数
    field_5: str | None = None  # 当前示数
    field_6: str | None = None  # 校验日期
    field_7: str | None = None  # 表计状态

class WeatherEntry(BaseModel):
    """气象数据明细结构。"""

    field_0: str | None = None  # 站点编号
    field_1: str | None = None  # 辐照度
    field_2: str | None = None  # 风速
    field_3: str | None = None  # 风向
    field_4: str | None = None  # 气温
    field_5: str | None = None  # 湿度
    field_6: str | None = None  # 降雨量
    field_7: str | None = None  # 记录时间

class GridConnectEntry(BaseModel):
    """调度指令明细结构。"""

    field_0: str | None = None  # 指令编号
    field_1: str | None = None  # 调度机构
    field_2: str | None = None  # 指令内容
    field_3: str | None = None  # 下发时间
    field_4: str | None = None  # 执行截止
    field_5: str | None = None  # 执行人员
    field_6: str | None = None  # 反馈情况
    field_7: str | None = None  # 指令状态

class CableEntry(BaseModel):
    """电缆段明细结构。"""

    field_0: str | None = None  # 电缆编号
    field_1: str | None = None  # 电缆型号
    field_2: str | None = None  # 起止位置
    field_3: str | None = None  # 敷设方式
    field_4: str | None = None  # 绝缘电阻
    field_5: str | None = None  # 上次测值
    field_6: str | None = None  # 测试日期
    field_7: str | None = None  # 电缆状态

class SecurityEntry(BaseModel):
    """安防记录明细结构。"""

    field_0: str | None = None  # 巡视编号
    field_1: str | None = None  # 巡视区域
    field_2: str | None = None  # 巡视人员
    field_3: str | None = None  # 巡视时间
    field_4: str | None = None  # 异常描述
    field_5: str | None = None  # 处理情况
    field_6: str | None = None  # 交接事项
    field_7: str | None = None  # 巡视状态

class MaintenanceEntry(BaseModel):
    """检修计划明细结构。"""

    field_0: str | None = None  # 计划编号
    field_1: str | None = None  # 设备名称
    field_2: str | None = None  # 检修级别
    field_3: str | None = None  # 计划日期
    field_4: str | None = None  # 检修班组
    field_5: str | None = None  # 检修时长
    field_6: str | None = None  # 验收结果
    field_7: str | None = None  # 计划状态

class DcBoxEntry(BaseModel):
    """汇流箱明细结构。"""

    field_0: str | None = None  # 汇流箱编号
    field_1: str | None = None  # 所属组串
    field_2: str | None = None  # 输入支路
    field_3: str | None = None  # 支路电流
    field_4: str | None = None  # 箱体温度
    field_5: str | None = None  # 通讯状态
    field_6: str | None = None  # 上次检修日
    field_7: str | None = None  # 箱体状态

class EnergySavingEntry(BaseModel):
    """能效报告明细结构。"""

    field_0: str | None = None  # 报告编号
    field_1: str | None = None  # 电站编号
    field_2: str | None = None  # 分析周期
    field_3: str | None = None  # 理论发电量
    field_4: str | None = None  # 实际发电量
    field_5: str | None = None  # 系统效率
    field_6: str | None = None  # 损失分析
    field_7: str | None = None  # 报告状态

class TrainingEntry(BaseModel):
    """培训记录明细结构。"""

    field_0: str | None = None  # 培训编号
    field_1: str | None = None  # 培训主题
    field_2: str | None = None  # 培训讲师
    field_3: str | None = None  # 培训日期
    field_4: str | None = None  # 参训人数
    field_5: str | None = None  # 考核通过
    field_6: str | None = None  # 培训资料
    field_7: str | None = None  # 培训状态

<template>
  <section class="page" data-module="inverter">
    <header class="page-head">
      <div>
        <h2>逆变器管理管理</h2>
        <p class="page-desc">维护逆变器，围绕逆变器编号、逆变器型号、额定功率、所属电站做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记逆变器</button>
        <button class="btn" type="button" @click="exportRows">导出逆变器管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <section class="ledger-panel">
      <h3>台账表格文件通道</h3>
      <p class="ledger-desc">
        先选择设备范围下载模板，按模板填入逆变器编号、型号、额定功率和所属电站后上传；
        系统只接收可识别的行，重复编号和功率格式不符的行会进入待修正清单。
      </p>

      <div class="ledger-step">
        <span class="step-title">1. 选择设备范围</span>
        <label v-for="plant in plantOptions" :key="plant" class="plant-option">
          <input v-model="selectedPlants" type="checkbox" :value="plant" /> {{ plant }}
        </label>
        <span v-if="!plantOptions.length" class="step-hint">暂无电站档案可选，模板将只含表头</span>
        <span v-else class="step-hint">不勾选时导出全部范围；空范围仍生成带表头的模板</span>
      </div>

      <div class="ledger-step">
        <span class="step-title">2. 下载模板并离线填写</span>
        <button class="btn" type="button" @click="downloadTemplate">下载台账模板</button>
      </div>

      <div class="ledger-step">
        <span class="step-title">3. 上传填好的表格文件</span>
        <input type="file" accept=".csv" @change="onFilePicked" />
        <button class="btn" type="button" :disabled="!ledgerFile" @click="uploadLedger">上传解析</button>
        <span v-if="ledgerFileName" class="step-hint">{{ ledgerFileName }}</span>
      </div>

      <div v-if="batchId" class="ledger-step">
        <span class="step-title">4. 解析结果（批次 {{ batchId }}）</span>
        <template v-if="acceptedRows.length">
          <h4 class="result-title">可接收 {{ acceptedRows.length }} 行</h4>
          <table class="data-table">
            <thead>
              <tr><th v-for="head in ledgerHeaders" :key="head">{{ head }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in acceptedRows" :key="idx">
                <td v-for="head in ledgerHeaders" :key="head">{{ row[head] }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <template v-if="pendingRows.length">
          <h4 class="result-title">待修正清单 {{ pendingRows.length }} 行</h4>
          <table class="data-table">
            <thead>
              <tr>
                <th>行号</th>
                <th v-for="head in ledgerHeaders" :key="head">{{ head }}</th>
                <th>待修正原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pendingRows" :key="item.line">
                <td>{{ item.line }}</td>
                <td v-for="head in ledgerHeaders" :key="head">{{ item.values[head] || '—' }}</td>
                <td class="error-text">{{ item.reasons.join('；') }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <div class="ledger-actions">
          <button
            class="btn primary"
            type="button"
            :disabled="ledgerConfirmed || !acceptedRows.length"
            @click="confirmLedger"
          >
            {{ ledgerConfirmed ? '已确认入库' : '确认入库' }}
          </button>
          <button class="btn" type="button" :disabled="!ledgerConfirmed" @click="downloadConfirmed">
            打包下载确认结果
          </button>
        </div>
      </div>

      <p v-if="ledgerMessage" class="ledger-message">{{ ledgerMessage }}</p>
    </section>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无逆变器管理数据，可先登记逆变器</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条逆变器管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null>
type PendingRow = { line: number; values: Record<string, string>; reasons: string[] }

const ENDPOINT = '/api/inverter'
const columns = ["逆变器编号", "逆变器型号", "额定功率", "所属电站", "投产日期", "运行时长", "告警次数", "运行状态"]
const actions = ["停机检查", "复位告警", "恢复运行"]
const statuses = ["运行", "待机", "告警", "停机", "维修中"]
const stats = [{"label": "运行中逆变器", "value": 0}, {"label": "告警逆变器", "value": 0}, {"label": "停机逆变器", "value": 0}]
const ledgerHeaders = ["逆变器编号", "逆变器型号", "额定功率", "所属电站"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const plantOptions = ref<string[]>([])
const selectedPlants = ref<string[]>([])
const ledgerFile = ref<File | null>(null)
const ledgerFileName = ref('')
const batchId = ref('')
const acceptedRows = ref<Row[]>([])
const pendingRows = ref<PendingRow[]>([])
const ledgerConfirmed = ref(false)
const ledgerMessage = ref('')

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '逆变器登记入口尚未接入审批流'
}

async function loadScope() {
  try {
    const payload = await fetchJson<{ plants: string[] }>(`${ENDPOINT}/ledger/scope`)
    plantOptions.value = payload.plants ?? []
  } catch {
    plantOptions.value = []
  }
}

function downloadTemplate() {
  const query = new URLSearchParams()
  for (const plant of selectedPlants.value) {
    query.append('plants', plant)
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  window.open(`${ENDPOINT}/ledger/template${suffix}`, '_blank')
}

function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  ledgerFile.value = input.files?.[0] ?? null
  ledgerFileName.value = ledgerFile.value?.name ?? ''
}

function resetBatch() {
  batchId.value = ''
  acceptedRows.value = []
  pendingRows.value = []
  ledgerConfirmed.value = false
}

async function uploadLedger() {
  if (!ledgerFile.value) {
    ledgerMessage.value = '请先选择要上传的表格文件'
    return
  }
  ledgerMessage.value = ''
  try {
    const content = await ledgerFile.value.text()
    const response = await request(`${ENDPOINT}/ledger/import`, {
      method: 'POST',
      body: JSON.stringify({ filename: ledgerFile.value.name, content }),
    })
    const payload = await response.json()
    ledgerMessage.value = payload.message ?? ''
    if (!payload.ok) {
      resetBatch()
      return
    }
    batchId.value = payload.batch_id ?? ''
    acceptedRows.value = payload.accepted ?? []
    pendingRows.value = payload.pending ?? []
    ledgerConfirmed.value = false
  } catch (error) {
    resetBatch()
    ledgerMessage.value = error instanceof Error ? error.message : '表格文件上传失败'
  }
}

async function confirmLedger() {
  if (!batchId.value) {
    return
  }
  try {
    const response = await request(`${ENDPOINT}/ledger/confirm`, {
      method: 'POST',
      body: JSON.stringify({ batch_id: batchId.value }),
    })
    const payload = await response.json()
    ledgerMessage.value = payload.message ?? ''
    if (payload.ok) {
      ledgerConfirmed.value = true
      await reload()
    }
  } catch (error) {
    ledgerMessage.value = error instanceof Error ? error.message : '确认入库失败'
  }
}

function downloadConfirmed() {
  if (!batchId.value) {
    return
  }
  window.open(`${ENDPOINT}/ledger/export?batch_id=${encodeURIComponent(batchId.value)}`, '_blank')
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('逆变器管理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '逆变器管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('逆变器列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '逆变器管理列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadScope()
})
</script>

<style scoped>
.ledger-panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 12px;
}
.ledger-panel h3 {
  margin: 0 0 4px;
  font-size: 14px;
}
.ledger-desc {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--muted);
}
.ledger-step {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-top: 1px dashed var(--border);
}
.ledger-step:first-of-type {
  border-top: none;
}
.step-title {
  font-size: 13px;
  font-weight: 600;
}
.step-hint {
  font-size: 12px;
  color: var(--muted);
}
.plant-option {
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.result-title {
  width: 100%;
  margin: 6px 0 0;
  font-size: 13px;
}
.ledger-actions {
  display: flex;
  gap: 10px;
  width: 100%;
}
.ledger-message {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--muted);
}
</style>

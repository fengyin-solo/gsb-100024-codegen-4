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

    <section class="sheet-channel">
      <h3 class="sheet-title">表格文件通道</h3>
      <p class="page-desc">
        先选设备范围生成模板，按模板填入逆变器编号、型号、额定功率和所属电站后上传；
        系统只接收可识别的行，重复编号与功率格式不符的行会进入待修正清单。
      </p>
      <div class="filter-bar">
        <label class="filter-item">
          <span>所属电站</span>
          <input v-model="scope.plant" placeholder="按电站圈定范围" />
        </label>
        <label class="filter-item">
          <span>运行状态</span>
          <select v-model="scope.status">
            <option value="">全部状态</option>
            <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>逆变器编号</span>
          <input v-model="scope.keyword" placeholder="按编号圈定范围" />
        </label>
        <button class="btn" type="button" @click="downloadTemplate">生成模板</button>
        <label class="btn upload-btn">
          上传表格
          <input type="file" accept=".csv,text/csv" hidden @change="onFilePicked" />
        </label>
      </div>
      <p v-if="sheetMessage" class="sheet-message">{{ sheetMessage }}</p>

      <template v-if="preview">
        <div v-if="preview.corrections.length" class="sheet-block">
          <h4>待修正清单（{{ preview.corrections.length }} 行）</h4>
          <table class="data-table">
            <thead>
              <tr>
                <th>行号</th>
                <th v-for="column in sheetColumns" :key="column">{{ column }}</th>
                <th>待修正原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in preview.corrections" :key="item.line">
                <td>{{ item.line }}</td>
                <td v-for="column in sheetColumns" :key="column">{{ item.values[column] || '—' }}</td>
                <td class="error-text">{{ item.reasons.join('、') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="preview.accepted.length" class="sheet-block">
          <h4>可接收行（{{ preview.accepted.length }} 行）</h4>
          <table class="data-table">
            <thead>
              <tr>
                <th v-for="column in sheetColumns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in preview.accepted" :key="index">
                <td v-for="column in sheetColumns" :key="column">{{ row[column] }}</td>
              </tr>
            </tbody>
          </table>
          <div class="sheet-actions">
            <button class="btn primary" type="button" @click="commitPreview">确认导入</button>
            <button class="btn ghost" type="button" @click="discardPreview">放弃本次上传</button>
          </div>
        </div>
      </template>

      <div v-if="confirmedRows.length" class="sheet-actions">
        <span>本次已确认 {{ confirmedRows.length }} 行，可打包成新的表格文件带回现场。</span>
        <button class="btn" type="button" @click="downloadConfirmed">打包下载确认结果</button>
      </div>
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

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type SheetRow = Record<string, string>
interface Correction {
  line: number
  values: SheetRow
  reasons: string[]
}
interface SheetPreview {
  accepted: SheetRow[]
  corrections: Correction[]
  discarded: number
}

const ENDPOINT = '/api/inverter'
const columns = ["逆变器编号", "逆变器型号", "额定功率", "所属电站", "投产日期", "运行时长", "告警次数", "运行状态"]
const actions = ["停机检查", "复位告警", "恢复运行"]
const statuses = ["运行", "待机", "告警", "停机", "维修中"]
const stats = [{"label": "运行中逆变器", "value": 0}, {"label": "告警逆变器", "value": 0}, {"label": "停机逆变器", "value": 0}]
const sheetColumns = ["逆变器编号", "逆变器型号", "额定功率", "所属电站"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const scope = ref({ plant: '', status: '', keyword: '' })
const preview = ref<SheetPreview | null>(null)
const confirmedRows = ref<SheetRow[]>([])
const sheetMessage = ref('')

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

async function downloadTemplate() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (scope.value.plant) params.set('plant', scope.value.plant)
  if (scope.value.status) params.set('status', scope.value.status)
  if (scope.value.keyword) params.set('keyword', scope.value.keyword)
  try {
    const response = await request(`${ENDPOINT}/sheet/template?${params.toString()}`)
    if (!response.ok) {
      throw new Error('模板生成失败，请稍后重试')
    }
    saveBlob(await response.blob(), '逆变器台账模板.csv')
    sheetMessage.value = '模板已生成，范围内无设备时也会带出表头'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板生成失败'
  }
}

async function onFilePicked(event: Event) {
  errorMessage.value = ''
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    const content = await file.text()
    const response = await request(`${ENDPOINT}/sheet/preview`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      preview.value = null
      sheetMessage.value = payload.message ?? '表格无法识别'
      return
    }
    preview.value = {
      accepted: payload.accepted ?? [],
      corrections: payload.corrections ?? [],
      discarded: payload.discarded ?? 0,
    }
    confirmedRows.value = []
    sheetMessage.value = payload.message ?? ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '表格上传失败'
  }
}

async function commitPreview() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/sheet/commit`, {
      method: 'POST',
      body: JSON.stringify({ rows: preview.value?.accepted ?? [] }),
    })
    const payload = await response.json()
    sheetMessage.value = payload.message ?? ''
    confirmedRows.value = payload.created ?? []
    preview.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '确认导入失败'
  }
}

function discardPreview() {
  preview.value = null
  sheetMessage.value = '已放弃本次上传，台账未改动'
}

async function downloadConfirmed() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/sheet/export`, {
      method: 'POST',
      body: JSON.stringify({ rows: confirmedRows.value }),
    })
    if (!response.ok) {
      throw new Error('打包失败，请稍后重试')
    }
    saveBlob(await response.blob(), '逆变器台账确认结果.csv')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '打包下载失败'
  }
}

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

onMounted(reload)
</script>

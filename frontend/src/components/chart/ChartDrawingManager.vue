<template>
  <div>
    <div v-if="drawings.length" class="drawing-manager">
      <div class="drawing-manager-head">
        <div class="drawing-manager-title">物件樹</div>
        <div class="drawing-manager-actions">
          <span class="drawing-shortcuts">快捷鍵：V 游標 / H 水平 / L 垂直 / T 趨勢 / A 箭頭 / F 費波 / R 區間 / M 測距 / N 註記 / B 框選 / Del 刪除 / Esc 取消</span>
          <button class="tool-btn compact" :disabled="!selectedDrawingId" @click="$emit('remove-selected-drawing')">刪除所選</button>
        </div>
      </div>
      <div class="drawing-list">
        <div
          v-for="drawing in drawings"
          :key="drawing.id || drawingLabel(drawing)"
          class="drawing-chip"
          :class="{ active: drawing.id === selectedDrawingId, muted: drawing.hidden, locked: drawing.locked }"
          @click="$emit('select-drawing', drawing.id)"
        >
          <span class="drawing-chip-type">{{ drawingTypeLabel(drawing.type) }}</span>
          <span class="drawing-chip-label">{{ drawingLabel(drawing) }}</span>
          <button
            class="drawing-chip-action"
            :class="{ active: !drawing.hidden }"
            :title="drawing.hidden ? '顯示物件' : '隱藏物件'"
            @click.stop="$emit('toggle-drawing-visibility', drawing.id)"
          >
            {{ drawing.hidden ? "隱" : "顯" }}
          </button>
          <button
            class="drawing-chip-action"
            :class="{ active: drawing.locked }"
            :title="drawing.locked ? '解除鎖定' : '鎖定物件'"
            @click.stop="$emit('toggle-drawing-lock', drawing.id)"
          >
            {{ drawing.locked ? "鎖" : "編" }}
          </button>
          <span class="drawing-chip-close" @click.stop="$emit('remove-drawing', drawing.id)">✕</span>
        </div>
      </div>
    </div>

    <div v-if="selectedDrawing" class="drawing-props">
      <div class="drawing-manager-head">
        <div class="drawing-manager-title">屬性面板</div>
        <div class="drawing-manager-actions">
          <span class="drawing-shortcuts">{{ drawingTypeLabel(selectedDrawing.type) }} / {{ drawingLabel(selectedDrawing) }}</span>
        </div>
      </div>
      <div class="drawing-prop-grid">
        <label class="drawing-prop">
          <span>顏色</span>
          <input class="drawing-color" type="color" :value="selectedDrawing.color || '#00d4ff'" @input="$emit('update-selected-drawing', { color: $event.target.value })" />
        </label>
        <label v-if="supportsLineWidth" class="drawing-prop">
          <span>線寬</span>
          <input class="drawing-range" type="range" min="1" max="5" step="0.5" :value="selectedDrawing.lineWidth || 1.5" @input="$emit('update-selected-drawing', { lineWidth: Number($event.target.value) })" />
          <strong>{{ Number(selectedDrawing.lineWidth || 1.5).toFixed(1) }}</strong>
        </label>
        <label v-if="supportsLineStyle" class="drawing-prop">
          <span>線型</span>
          <select class="drawing-select" :value="selectedDrawing.lineStyle || 'solid'" @change="$emit('update-selected-drawing', { lineStyle: $event.target.value })">
            <option value="solid">實線</option>
            <option value="dash">虛線</option>
            <option value="dot">點線</option>
          </select>
        </label>
        <label class="drawing-prop wide">
          <span>標籤</span>
          <input class="drawing-text" type="text" :value="selectedDrawing.label || ''" placeholder="可選，顯示在圖上的說明" @input="$emit('update-selected-drawing', { label: $event.target.value })" />
        </label>
        <label v-if="supportsText" class="drawing-prop wide">
          <span>註記文字</span>
          <input class="drawing-text" type="text" :value="selectedDrawing.text || ''" placeholder="編輯註記內容" @input="$emit('update-selected-drawing', { text: $event.target.value })" />
        </label>
        <label v-if="supportsFillOpacity" class="drawing-prop">
          <span>填色透明</span>
          <input class="drawing-range" type="range" min="0.05" max="0.95" step="0.05" :value="selectedDrawing.fillOpacity || 0.12" @input="$emit('update-selected-drawing', { fillOpacity: Number($event.target.value) })" />
          <strong>{{ Math.round((selectedDrawing.fillOpacity || 0.12) * 100) }}%</strong>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  drawings: { type: Array, default: () => [] },
  selectedDrawingId: { type: String, default: null },
  selectedDrawing: { type: Object, default: null },
  supportsLineWidth: { type: Boolean, default: false },
  supportsLineStyle: { type: Boolean, default: false },
  supportsFillOpacity: { type: Boolean, default: false },
  supportsText: { type: Boolean, default: false },
  drawingTypeLabel: { type: Function, required: true },
  drawingLabel: { type: Function, required: true },
});

defineEmits([
  "select-drawing",
  "toggle-drawing-visibility",
  "toggle-drawing-lock",
  "remove-drawing",
  "update-selected-drawing",
  "remove-selected-drawing",
]);
</script>

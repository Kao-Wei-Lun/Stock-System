<template>
  <div>
    <div class="workspace-toolbar">
      <span class="tool-label">工作區：</span>
      <input
        :value="workspacePresetName"
        class="compare-input workspace-input"
        type="text"
        placeholder="輸入名稱後儲存目前分析版面"
        @input="$emit('update:workspacePresetName', $event.target.value)"
        @keydown.enter.prevent="$emit('save-workspace')"
      />
      <button class="tool-btn" @click="$emit('save-workspace')">儲存</button>
      <select
        :value="workspaceSelection"
        class="workspace-select"
        @change="$emit('update:workspaceSelection', resolveSelectionValue($event.target.value))"
      >
        <option value="">選擇已儲存工作區</option>
        <option
          v-for="preset in workspacePresets"
          :key="preset.id"
          :value="preset.id"
        >
          {{ preset.name }}
        </option>
      </select>
      <button class="tool-btn" :disabled="!workspaceSelection" @click="$emit('load-workspace')">載入</button>
      <button class="tool-btn" :disabled="!workspaceSelection" @click="$emit('delete-workspace')">刪除</button>
    </div>

    <div class="compare-toolbar">
      <span class="tool-label">比較：</span>
      <input
        :value="compareInput"
        class="compare-input"
        type="text"
        placeholder="輸入代號加入比較，例如 MSFT / 0050"
        @input="$emit('update:compareInput', $event.target.value)"
        @keydown.enter.prevent="$emit('submit-compare')"
      />
      <button class="tool-btn" @click="$emit('submit-compare')">加入比較</button>
      <button class="tool-btn" :class="{ active: comparisonMode === 'percent' }" @click="$emit('set-compare-mode', 'percent')">相對報酬</button>
      <button class="tool-btn" :class="{ active: comparisonMode === 'price' }" @click="$emit('set-compare-mode', 'price')">絕對價格</button>
      <button class="tool-btn" :disabled="!compareSeries.length" @click="$emit('clear-compare')">清空比較</button>
    </div>

    <div v-if="showComparePanel" class="compare-legend">
      <button
        v-for="series in compareSeries"
        :key="series.ticker"
        class="compare-chip"
        :style="{ '--compare-color': series.color }"
        @click="$emit('remove-compare', series.ticker)"
      >
        <span class="compare-chip-line"></span>
        <span>{{ series.ticker }}</span>
        <span :class="series.changePct >= 0 ? 'up' : 'dn'">
          {{ series.changePct >= 0 ? "+" : "" }}{{ Number(series.changePct || 0).toFixed(2) }}%
        </span>
        <span class="compare-chip-close">✕</span>
      </button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  workspacePresetName: { type: String, default: "" },
  workspaceSelection: { type: [String, Number], default: "" },
  workspacePresets: { type: Array, default: () => [] },
  compareInput: { type: String, default: "" },
  comparisonMode: { type: String, default: "percent" },
  compareSeries: { type: Array, default: () => [] },
  showComparePanel: { type: Boolean, default: false },
});

defineEmits([
  "update:workspacePresetName",
  "update:workspaceSelection",
  "save-workspace",
  "load-workspace",
  "delete-workspace",
  "update:compareInput",
  "submit-compare",
  "set-compare-mode",
  "clear-compare",
  "remove-compare",
]);

function resolveSelectionValue(rawValue) {
  const matchedPreset = props.workspacePresets.find((preset) => String(preset.id) === String(rawValue));
  return matchedPreset ? matchedPreset.id : rawValue;
}
</script>

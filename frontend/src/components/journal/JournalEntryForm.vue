<template>
  <div class="journal-card">
    <div class="bt-section-title">{{ journalForm.id ? "編輯紀錄" : "新增紀錄" }}</div>
    <div class="bt-row"><div class="bt-label">Ticker</div><input class="bt-inp" :value="journalForm.ticker" @input="$emit('update-journal-field', { key: 'ticker', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">市場</div><input class="bt-inp" :value="journalForm.market" @input="$emit('update-journal-field', { key: 'market', value: $event.target.value })"></div>
    <div class="bt-row">
      <div class="bt-label">方向</div>
      <select class="bt-sel" :value="journalForm.direction" @change="$emit('update-journal-field', { key: 'direction', value: $event.target.value })">
        <option value="long">Long</option>
        <option value="short">Short</option>
      </select>
    </div>
    <div class="bt-row"><div class="bt-label">策略碼</div><input class="bt-inp" :value="journalForm.strategy_code" @input="$emit('update-journal-field', { key: 'strategy_code', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">進場時間</div><input class="bt-inp" type="datetime-local" :value="journalForm.entry_time" @input="$emit('update-journal-field', { key: 'entry_time', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">進場價格</div><input class="bt-inp" type="number" :value="journalForm.entry_price" @input="$emit('update-journal-field', { key: 'entry_price', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">出場時間</div><input class="bt-inp" type="datetime-local" :value="journalForm.exit_time" @input="$emit('update-journal-field', { key: 'exit_time', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">出場價格</div><input class="bt-inp" type="number" :value="journalForm.exit_price" @input="$emit('update-journal-field', { key: 'exit_price', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">部位</div><input class="bt-inp" type="number" :value="journalForm.size" @input="$emit('update-journal-field', { key: 'size', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">停損</div><input class="bt-inp" type="number" :value="journalForm.stop_loss" @input="$emit('update-journal-field', { key: 'stop_loss', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">停利</div><input class="bt-inp" type="number" :value="journalForm.take_profit" @input="$emit('update-journal-field', { key: 'take_profit', value: $event.target.value })"></div>
    <div class="bt-row"><div class="bt-label">標籤</div><input class="bt-inp" :value="journalForm.tags_text" @input="$emit('update-journal-field', { key: 'tags_text', value: $event.target.value })" placeholder="breakout, earnings"></div>
    <div class="bt-row"><div class="bt-label">情緒</div><input class="bt-inp" :value="journalForm.emotion_tag" @input="$emit('update-journal-field', { key: 'emotion_tag', value: $event.target.value })" placeholder="calm"></div>
    <div class="journal-text-row">
      <div class="bt-label">進場理由</div>
      <textarea class="journal-textarea" :value="journalForm.entry_reason" @input="$emit('update-journal-field', { key: 'entry_reason', value: $event.target.value })"></textarea>
    </div>
    <div class="journal-text-row">
      <div class="bt-label">出場理由</div>
      <textarea class="journal-textarea" :value="journalForm.exit_reason" @input="$emit('update-journal-field', { key: 'exit_reason', value: $event.target.value })"></textarea>
    </div>
    <div class="journal-text-row">
      <div class="bt-label">檢討</div>
      <textarea class="journal-textarea" :value="journalForm.review_notes" @input="$emit('update-journal-field', { key: 'review_notes', value: $event.target.value })"></textarea>
    </div>

    <div class="bt-row"><div class="bt-label">附件路徑</div><input class="bt-inp" :value="journalForm.attachment_path" @input="$emit('update-journal-field', { key: 'attachment_path', value: $event.target.value })" placeholder="C:/screenshots/trade.png"></div>
    <div class="bt-row"><div class="bt-label">附件類型</div><input class="bt-inp" :value="journalForm.attachment_type" @input="$emit('update-journal-field', { key: 'attachment_type', value: $event.target.value })" placeholder="image/png"></div>
    <button class="add-btn" style="margin-top:0" @click="$emit('add-journal-attachment')">＋ 加入附件</button>
    <div v-if="journalForm.attachments?.length" class="journal-attachment-list">
      <div v-for="(attachment, index) in journalForm.attachments" :key="`${attachment.file_path}-${index}`" class="bt-trade-row">
        <div>
          <div>{{ attachment.file_path }}</div>
          <div class="bt-trade-sub">{{ attachment.file_type || "metadata only" }}</div>
        </div>
        <button class="journal-inline-btn" @click="$emit('remove-journal-attachment', index)">移除</button>
      </div>
    </div>

    <div class="journal-action-row">
      <button class="run-btn" :disabled="journalLoading" @click="$emit('save-journal-entry')">{{ journalLoading ? "儲存中..." : (journalForm.id ? "更新交易紀錄" : "建立交易紀錄") }}</button>
      <button class="sync-btn" type="button" @click="$emit('reset-journal-form')">清空表單</button>
      <button v-if="journalForm.id" class="sync-btn" type="button" @click="$emit('delete-journal-entry', journalForm.id)">刪除紀錄</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  journalForm: { type: Object, required: true },
  journalLoading: { type: Boolean, required: true },
});

defineEmits([
  "update-journal-field",
  "add-journal-attachment",
  "remove-journal-attachment",
  "save-journal-entry",
  "reset-journal-form",
  "delete-journal-entry",
]);
</script>

<template>
  <div class="intel-shell">
    <section class="intel-panel">
      <div class="intel-head">
        <div>
          <div class="intel-title">事件中心</div>
          <div class="intel-subtitle">近期市場事件與目前標的事件風險</div>
        </div>
        <div class="intel-head-actions">
          <button class="intel-btn secondary" @click="$emit('create-alert', buildTickerEventAlert())">事件提醒</button>
          <button class="intel-btn" @click="$emit('refresh-events')">重新整理</button>
        </div>
      </div>

      <div class="intel-grid two-col">
        <div class="intel-card">
          <div class="card-title">市場事件日曆</div>
          <div v-if="calendarEvents.length" class="event-list">
            <button
              v-for="item in calendarEvents"
              :key="`${item.ticker || 'market'}-${item.event_type}-${item.event_date}`"
              type="button"
              class="event-row"
              @click="item.ticker && $emit('open-ticker', item.ticker)"
            >
              <span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.ticker || "MARKET" }} · {{ item.event_date }}</small>
              </span>
              <span class="event-tag" :class="item.importance || 'medium'">{{ importanceLabel(item.importance) }}</span>
            </button>
          </div>
          <div v-else class="empty-state">目前沒有已同步的事件資料</div>
        </div>

        <div class="intel-card">
          <div class="card-title">{{ currentTicker }} 事件焦點</div>
          <div v-if="tickerEvents.length" class="event-list">
            <div v-for="item in tickerEvents" :key="`${item.event_type}-${item.event_date}`" class="event-row static">
              <span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.event_date }} · {{ item.description || item.event_type }}</small>
              </span>
              <span class="event-tag" :class="item.importance || 'medium'">{{ importanceLabel(item.importance) }}</span>
            </div>
          </div>
          <div v-else class="empty-state">目前標的尚未同步到事件資料</div>
        </div>
      </div>
    </section>

    <section class="intel-panel">
      <div class="intel-head">
        <div>
          <div class="intel-title">新聞快照</div>
          <div class="intel-subtitle">{{ currentName || currentTicker }} 近期新聞</div>
        </div>
        <button class="intel-btn" @click="$emit('refresh-news')">重新整理</button>
      </div>
      <div v-if="tickerNews.length" class="news-list">
        <a
          v-for="article in tickerNews"
          :key="`${article.title}-${article.published_at}`"
          class="news-card"
          :href="article.url"
          target="_blank"
          rel="noreferrer"
        >
          <div class="card-title">{{ article.title }}</div>
          <div class="news-meta">{{ article.source || "news" }} · {{ formatTs(article.published_at) }}</div>
          <p>{{ article.summary || "點擊查看完整內容" }}</p>
        </a>
      </div>
      <div v-else class="empty-state">目前標的尚未同步到新聞資料</div>
    </section>
  </div>
</template>

<script setup>
const props = defineProps({
  currentTicker: { type: String, required: true },
  currentName: { type: String, default: "" },
  calendarEvents: { type: Array, default: () => [] },
  tickerEvents: { type: Array, default: () => [] },
  tickerNews: { type: Array, default: () => [] },
});

defineEmits(["refresh-events", "refresh-news", "open-ticker", "create-alert"]);

function daysUntil(value) {
  if (!value) return null;
  const target = new Date(`${value}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86400000);
}

function buildTickerEventAlert() {
  const nextItem = props.tickerEvents.find((item) => item?.event_date) || null;
  const days = daysUntil(nextItem?.event_date);
  const suggestedDays = Number.isFinite(days) ? Math.max(Math.min(days, 7), 1) : 7;
  const targetName = props.currentName || props.currentTicker;
  return {
    ticker: props.currentTicker,
    type: "event",
    condition: "within_days",
    value: String(suggestedDays),
    event_type: nextItem?.event_type || "",
    event_title: nextItem?.title || "",
    importance: nextItem?.importance || "",
    event_scope: "ticker",
    target_label: targetName,
    prefill_hint: nextItem
      ? `事件提醒將追蹤 ${nextItem.title}（${nextItem.event_date}）。`
      : `${targetName} 事件提醒會監控未來幾日的新事件。`,
    context_tags: ["事件提醒", targetName].filter(Boolean),
  };
}

function formatTs(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-TW", { hour12: false });
}

function importanceLabel(value) {
  if (value === "high") return "高";
  if (value === "low") return "低";
  return "中";
}
</script>

<style scoped>
.intel-shell {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  background: linear-gradient(180deg, rgba(8, 12, 18, 0.98) 0%, rgba(12, 18, 28, 0.98) 100%);
}

.intel-panel,
.intel-card,
.news-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(9, 12, 19, 0.86);
  border-radius: 14px;
}

.intel-panel {
  padding: 16px;
}

.intel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.intel-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.intel-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text1);
}

.intel-subtitle {
  font-size: 12px;
  color: var(--text3);
  margin-top: 4px;
}

.intel-btn {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text2);
  border-radius: 999px;
  padding: 8px 12px;
  cursor: pointer;
}

.intel-btn.secondary {
  background: rgba(0, 212, 255, 0.08);
  color: #9fe7ff;
}

.intel-grid {
  display: grid;
  gap: 14px;
}

.two-col {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.intel-card {
  padding: 14px;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text1);
  margin-bottom: 10px;
}

.event-list,
.news-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.event-row,
.news-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  text-align: left;
  padding: 12px;
  color: inherit;
  text-decoration: none;
}

.event-row {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  cursor: pointer;
}

.event-row.static {
  cursor: default;
}

.event-row strong,
.news-card .card-title {
  display: block;
  margin-bottom: 4px;
}

.event-row small,
.news-meta {
  color: var(--text3);
  font-size: 11px;
}

.event-tag {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  color: #081018;
  background: #f6c85f;
}

.event-tag.high {
  background: #ff7b72;
}

.event-tag.low {
  background: #87d37c;
}

.news-card {
  align-items: flex-start;
  flex-direction: column;
}

.news-card p {
  margin: 6px 0 0;
  color: var(--text2);
  line-height: 1.6;
  font-size: 12px;
}

.empty-state {
  padding: 18px;
  text-align: center;
  color: var(--text3);
  font-size: 12px;
}

@media (max-width: 720px) {
  .intel-shell {
    gap: 12px;
    padding: 12px;
  }

  .intel-panel,
  .intel-card {
    padding: 12px;
  }

  .intel-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .intel-btn {
    width: 100%;
  }

  .two-col {
    grid-template-columns: 1fr;
  }

  .event-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .event-tag {
    align-self: flex-start;
  }
}
</style>

import { nextTick, onBeforeUnmount, onMounted, reactive, unref, watch } from "vue";

export function useChartSyncPanes({
  layoutPanes,
  visibleData,
  viewportStartIndex,
  crosshair,
}) {
  const syncPaneRefs = reactive({});
  let syncPaneFrame = 0;

  function setSyncPaneRef(key, element) {
    if (element) syncPaneRefs[key] = element;
    else delete syncPaneRefs[key];
    scheduleSyncPaneRender();
  }

  function formatPaneDateLabel(dateString, range = 0) {
    if (!dateString) return "";
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return dateString.slice(5);
    if (range > 540) {
      return `${String(date.getFullYear()).slice(2)}/${String(date.getMonth() + 1).padStart(2, "0")}`;
    }
    return `${String(date.getFullYear()).slice(2)}/${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}`;
  }

  function getPaneTickIndices(data, count = 5) {
    if (!data.length) return [];
    const indices = new Set([0, data.length - 1]);
    const step = Math.max(1, Math.floor((data.length - 1) / Math.max(count - 1, 1)));
    for (let index = 0; index < data.length; index += step) {
      indices.add(index);
    }
    return [...indices].sort((left, right) => left - right);
  }

  function resizeSyncPaneCanvas(canvas) {
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const { clientWidth, clientHeight } = canvas;
    canvas.width = Math.max(1, clientWidth * dpr);
    canvas.height = Math.max(1, clientHeight * dpr);
    canvas.style.width = `${clientWidth}px`;
    canvas.style.height = `${clientHeight}px`;
  }

  function drawSyncPane(canvas, pane) {
    const rows = unref(visibleData) || [];
    if (!canvas || !rows.length) {
      if (canvas) {
        const ctx = canvas.getContext("2d");
        const dpr = window.devicePixelRatio || 1;
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
      }
      return;
    }

    resizeSyncPaneCanvas(canvas);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width / dpr;
    const height = canvas.height / dpr;
    const pad = { top: 18, right: 12, bottom: 20, left: 10 };
    const data = rows;
    const chartWidth = width - pad.left - pad.right;
    const chartHeight = height - pad.top - pad.bottom;
    const step = chartWidth / Math.max(data.length, 1);
    const barWidth = Math.max(1.5, step * 0.68);
    const xAt = (index) => pad.left + (index + 0.5) * step;
    const highs = data.map((row) => row.high);
    const lows = data.map((row) => row.low);
    const rawMin = Math.min(...lows);
    const rawMax = Math.max(...highs);
    const padValue = Math.max((rawMax - rawMin) * 0.12, Math.abs(rawMax) * 0.02, 0.05);
    const min = rawMin - padValue;
    const max = rawMax + padValue;
    const scaleY = (value) => pad.top + (1 - (value - min) / (max - min || 1)) * chartHeight;
    const rangeDays = data.length > 1
      ? Math.abs((new Date(data[data.length - 1].date) - new Date(data[0].date)) / 86400000)
      : 0;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "rgba(8,12,18,0.96)";
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = "rgba(30,45,61,0.72)";
    ctx.lineWidth = 0.5;
    [0, 0.33, 0.66, 1].forEach((ratio) => {
      const y = pad.top + chartHeight * ratio;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
    });

    const closes = data.map((row) => row.close);
    if (pane.mode === "candles") {
      data.forEach((row, index) => {
        const x = xAt(index);
        const isUp = row.close >= row.open;
        const color = isUp ? "#00d9a3" : "#ff4d6a";
        ctx.strokeStyle = color;
        ctx.fillStyle = isUp ? "rgba(0,217,163,0.88)" : "rgba(255,77,106,0.88)";
        ctx.beginPath();
        ctx.moveTo(x, scaleY(row.high));
        ctx.lineTo(x, scaleY(row.low));
        ctx.stroke();
        const top = scaleY(Math.max(row.open, row.close));
        const bottom = scaleY(Math.min(row.open, row.close));
        ctx.fillRect(x - barWidth / 2, top, barWidth, Math.max(1, bottom - top));
      });
    } else {
      ctx.beginPath();
      closes.forEach((value, index) => {
        if (index === 0) ctx.moveTo(xAt(index), scaleY(value));
        else ctx.lineTo(xAt(index), scaleY(value));
      });
      if (pane.mode === "area") {
        ctx.lineTo(xAt(data.length - 1), height - pad.bottom);
        ctx.lineTo(xAt(0), height - pad.bottom);
        ctx.closePath();
        ctx.fillStyle = "rgba(0,212,255,0.12)";
        ctx.fill();
        ctx.beginPath();
        closes.forEach((value, index) => {
          if (index === 0) ctx.moveTo(xAt(index), scaleY(value));
          else ctx.lineTo(xAt(index), scaleY(value));
        });
      }
      ctx.strokeStyle = pane.mode === "area" ? "#00d4ff" : "#8dc1ff";
      ctx.lineWidth = 1.6;
      ctx.stroke();
    }

    const tickIndices = getPaneTickIndices(data, 4);
    ctx.fillStyle = "rgba(99,123,148,0.9)";
    ctx.font = "9px JetBrains Mono";
    tickIndices.forEach((index) => {
      const x = xAt(index);
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, height - pad.bottom);
      ctx.strokeStyle = "rgba(30,45,61,0.5)";
      ctx.stroke();
      const label = formatPaneDateLabel(data[index].date, rangeDays);
      ctx.fillText(label, Math.max(pad.left, x - Math.max(16, label.length * 3.4)), height - 5);
    });

    const currentCrosshair = unref(crosshair) || {};
    const startIndex = unref(viewportStartIndex) || 0;
    if (
      currentCrosshair.visible
      && Number.isInteger(currentCrosshair.absoluteIndex)
      && currentCrosshair.absoluteIndex >= startIndex
      && currentCrosshair.absoluteIndex < startIndex + data.length
    ) {
      const localIndex = currentCrosshair.absoluteIndex - startIndex;
      const x = xAt(localIndex);
      ctx.strokeStyle = "rgba(255,209,102,0.95)";
      ctx.setLineDash([5, 3]);
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, height - pad.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      const label = formatPaneDateLabel(data[localIndex]?.date, rangeDays);
      const labelWidth = Math.max(44, label.length * 8 + 10);
      const left = Math.min(Math.max(pad.left, x - labelWidth / 2), width - pad.right - labelWidth);
      ctx.fillStyle = "rgba(255,209,102,0.16)";
      ctx.fillRect(left, 2, labelWidth, 14);
      ctx.strokeStyle = "rgba(255,209,102,0.88)";
      ctx.strokeRect(left, 2, labelWidth, 14);
      ctx.fillStyle = "#ffd166";
      ctx.fillText(label, left + 6, 12);
    }
  }

  function renderSyncPanes() {
    (unref(layoutPanes) || []).forEach((pane) => {
      drawSyncPane(syncPaneRefs[pane.key], pane);
    });
  }

  function scheduleSyncPaneRender() {
    if (typeof window === "undefined") return;
    if (syncPaneFrame) cancelAnimationFrame(syncPaneFrame);
    syncPaneFrame = window.requestAnimationFrame(() => {
      syncPaneFrame = 0;
      renderSyncPanes();
    });
  }

  watch(
    () => ({
      panes: unref(layoutPanes),
      rows: unref(visibleData),
      startIndex: unref(viewportStartIndex),
      crosshair: unref(crosshair),
    }),
    () => scheduleSyncPaneRender(),
    { deep: true },
  );

  onMounted(() => {
    if (typeof window === "undefined") return;
    window.addEventListener("resize", scheduleSyncPaneRender);
    nextTick(() => scheduleSyncPaneRender());
  });

  onBeforeUnmount(() => {
    if (typeof window !== "undefined") {
      window.removeEventListener("resize", scheduleSyncPaneRender);
    }
    if (syncPaneFrame) cancelAnimationFrame(syncPaneFrame);
  });

  return {
    setSyncPaneRef,
    scheduleSyncPaneRender,
  };
}

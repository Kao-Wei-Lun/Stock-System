import { nextTick, onBeforeUnmount, onMounted, watch } from "vue";

import {
  calcBB,
  calcEMA,
  calcMACD,
  calcMA,
  calcRSI,
  calcStoch,
  calcVWAP,
} from "../utils/indicatorUtils";
import { fmtPrice, fmtVol } from "../utils/formatters";

const PAD = { top: 20, right: 70, bottom: 22, left: 10 };

export function useChartEngine({
  mainCanvas,
  volumeCanvas,
  rsiCanvas,
  macdCanvas,
  stochCanvas,
  chartAreaRef,
  props,
  emit,
}) {
  const getDpr = () => window.devicePixelRatio || 1;
  const canvasWidth = (canvas) => canvas.width / getDpr();
  const canvasHeight = (canvas) => canvas.height / getDpr();
  const setupCtx = (ctx) => ctx.setTransform(getDpr(), 0, 0, getDpr(), 0, 0);

  const barLayout = (canvas, count) => {
    const width = canvasWidth(canvas) - PAD.left - PAD.right;
    const barWidth = Math.max(1, (width / count) * 0.7);
    const barX = (index) => PAD.left + (index + 0.5) * (width / count);
    return { width, barWidth, barX };
  };

  const priceScale = (data, extras = []) => {
    const prices = data.flatMap((row) => [row.high, row.low, ...extras]).filter((value) => value != null);
    return {
      min: Math.min(...prices) * 0.998,
      max: Math.max(...prices) * 1.002,
    };
  };

  const scaleY = (value, min, max, topPad, chartHeight) => topPad + (1 - (value - min) / (max - min)) * chartHeight;

  const drawLine = (ctx, values, barX, scale, color, lineWidth = 1.5) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    let started = false;
    values.forEach((value, index) => {
      if (value == null) return;
      if (!started) {
        ctx.moveTo(barX(index), scale(value));
        started = true;
      } else {
        ctx.lineTo(barX(index), scale(value));
      }
    });
    ctx.stroke();
  };

  const drawGrid = (ctx, canvas, min, max, steps = 5) => {
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const chartHeight = height - PAD.top - PAD.bottom;

    ctx.strokeStyle = "rgba(30,45,61,0.7)";
    ctx.lineWidth = 0.5;
    ctx.fillStyle = "rgba(77,102,128,0.7)";
    ctx.font = "9px JetBrains Mono";

    for (let index = 0; index <= steps; index += 1) {
      const y = PAD.top + index * (chartHeight / steps);
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(width - PAD.right, y);
      ctx.stroke();
      const price = max - (index * (max - min)) / steps;
      ctx.fillText(price.toFixed(2), width - PAD.right + 4, y + 3);
    }
  };

  const clearAll = () => {
    [mainCanvas.value, volumeCanvas.value, rsiCanvas.value, macdCanvas.value, stochCanvas.value]
      .filter(Boolean)
      .forEach((canvas) => {
        const ctx = canvas.getContext("2d");
        setupCtx(ctx);
        ctx.clearRect(0, 0, canvasWidth(canvas), canvasHeight(canvas));
      });
  };

  const renderMain = () => {
    if (!mainCanvas.value || !props.ohlcData.length) return;
    const canvas = mainCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const data = props.ohlcData;
    const count = data.length;
    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const chartHeight = height - PAD.top - PAD.bottom;
    const { barX, barWidth } = barLayout(canvas, count);
    const bb = props.activeInd.bb ? calcBB(data) : null;
    const extras = [];
    if (bb) {
      bb.forEach((band) => {
        if (band.u != null) extras.push(band.u, band.l);
      });
    }
    const { min, max } = priceScale(data, extras);
    const scale = (value) => scaleY(value, min, max, PAD.top, chartHeight);

    drawGrid(ctx, canvas, min, max);

    if (props.activeInd.ma20) drawLine(ctx, calcMA(data, 20), barX, scale, "#3b8bff", 1.5);
    if (props.activeInd.ma50) drawLine(ctx, calcMA(data, 50), barX, scale, "#f5a623", 1.5);
    if (props.activeInd.ma200) drawLine(ctx, calcMA(data, 200), barX, scale, "#9b6dff", 1.5);
    if (props.activeInd.ema12) drawLine(ctx, calcEMA(data, 12), barX, scale, "#00d4ff", 1);
    if (props.activeInd.vwap) drawLine(ctx, calcVWAP(data), barX, scale, "#ff8c42", 1.2);

    if (bb) {
      const upper = bb.map((band) => band.u);
      const lower = bb.map((band) => band.l);
      drawLine(ctx, upper, barX, scale, "#ffd166", 0.8);
      drawLine(ctx, lower, barX, scale, "#ffd166", 0.8);
    }

    data.forEach((row, index) => {
      const x = barX(index);
      const isUp = row.close >= row.open;
      const color = isUp ? "#00d9a3" : "#ff4d6a";
      ctx.strokeStyle = color;
      ctx.fillStyle = isUp ? "rgba(0,217,163,0.85)" : "rgba(255,77,106,0.85)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, scale(row.high));
      ctx.lineTo(x, scale(row.low));
      ctx.stroke();
      const top = scale(Math.max(row.open, row.close));
      const bottom = scale(Math.min(row.open, row.close));
      ctx.fillRect(x - barWidth / 2, top, barWidth, Math.max(1, bottom - top));
    });

    props.drawings.forEach((drawing) => {
      if (drawing.type === "buy" || drawing.type === "sell") {
        const x = barX(drawing.index);
        ctx.fillStyle = drawing.type === "buy" ? "#00d9a3" : "#ff4d6a";
        ctx.font = "bold 13px sans-serif";
        const y = drawing.type === "buy" ? scale(data[drawing.index].low) + 14 : scale(data[drawing.index].high) - 6;
        ctx.fillText(drawing.type === "buy" ? "▲" : "▼", x - 5, y);
      }
      if (drawing.type === "hline") {
        ctx.strokeStyle = "#f5a623";
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 3]);
        ctx.beginPath();
        ctx.moveTo(PAD.left, scale(drawing.price));
        ctx.lineTo(width - PAD.right, scale(drawing.price));
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#f5a623";
        ctx.font = "9px JetBrains Mono";
        ctx.fillText(drawing.price.toFixed(2), width - PAD.right + 2, scale(drawing.price) + 3);
      }
    });

    ctx.fillStyle = "rgba(77,102,128,0.7)";
    ctx.font = "9px JetBrains Mono";
    const step = Math.max(1, Math.floor(count / 8));
    for (let index = 0; index < count; index += step) {
      ctx.fillText(data[index].date.slice(5), barX(index) - 14, height - 8);
    }
  };

  const renderVolume = () => {
    if (!volumeCanvas.value || !props.ohlcData.length) return;
    const canvas = volumeCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const data = props.ohlcData;
    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const { barX, barWidth } = barLayout(canvas, data.length);
    const maxVolume = Math.max(...data.map((row) => row.volume));
    const chartHeight = height - 4;
    data.forEach((row, index) => {
      const barHeight = (row.volume / maxVolume) * chartHeight;
      ctx.fillStyle = row.close >= row.open ? "rgba(0,217,163,0.4)" : "rgba(255,77,106,0.4)";
      ctx.fillRect(barX(index) - (barWidth * 0.75) / 2, chartHeight - barHeight + 2, barWidth * 0.75, barHeight);
    });
    ctx.fillStyle = "rgba(77,102,128,0.5)";
    ctx.font = "9px JetBrains Mono";
    ctx.fillText("VOL", 2, 12);
  };

  const renderRsi = () => {
    if (!rsiCanvas.value || !props.ohlcData.length || !props.activePanels.rsi) return;
    const canvas = rsiCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const { barX } = barLayout(canvas, props.ohlcData.length);
    const chartHeight = height - 8;
    const scale = (value) => 4 + (1 - value / 100) * chartHeight;

    ctx.fillStyle = "rgba(255,77,106,0.05)";
    ctx.fillRect(PAD.left, scale(100), width - PAD.left - PAD.right, scale(70) - scale(100));
    ctx.fillStyle = "rgba(0,217,163,0.05)";
    ctx.fillRect(PAD.left, scale(30), width - PAD.left - PAD.right, scale(0) - scale(30));

    [70, 50, 30].forEach((level) => {
      ctx.strokeStyle = "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.setLineDash(level === 50 ? [4, 4] : []);
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(level));
      ctx.lineTo(width - PAD.right, scale(level));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(77,102,128,0.6)";
      ctx.font = "8px JetBrains Mono";
      ctx.fillText(level, width - PAD.right + 2, scale(level) + 3);
    });

    drawLine(ctx, calcRSI(props.ohlcData), barX, scale, "#00d9a3", 1.5);
  };

  const renderMacd = () => {
    if (!macdCanvas.value || !props.ohlcData.length || !props.activePanels.macd) return;
    const canvas = macdCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const { macd, signal, hist } = calcMACD(props.ohlcData);
    const { barX, barWidth } = barLayout(canvas, props.ohlcData.length);
    const values = [...hist, ...macd, ...signal].filter((value) => value != null);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const chartHeight = height - 8;
    const scale = (value) => 4 + (1 - (value - min) / (max - min || 1)) * chartHeight;

    ctx.strokeStyle = "rgba(77,102,128,0.4)";
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(PAD.left, scale(0));
    ctx.lineTo(width - PAD.right, scale(0));
    ctx.stroke();

    hist.forEach((value, index) => {
      if (value == null) return;
      ctx.fillStyle = value >= 0 ? "rgba(0,217,163,0.5)" : "rgba(255,77,106,0.5)";
      const top = scale(Math.max(0, value));
      const bottom = scale(Math.min(0, value));
      ctx.fillRect(barX(index) - barWidth / 2, top, barWidth, Math.max(1, bottom - top));
    });

    drawLine(ctx, macd, barX, scale, "#3b8bff", 1.2);
    drawLine(ctx, signal, barX, scale, "#f5a623", 1.2);
  };

  const renderStoch = () => {
    if (!stochCanvas.value || !props.ohlcData.length || !props.activePanels.stoch) return;
    const canvas = stochCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const { k, d } = calcStoch(props.ohlcData);
    const { barX } = barLayout(canvas, props.ohlcData.length);
    const chartHeight = height - 8;
    const scale = (value) => 4 + (1 - value / 100) * chartHeight;

    [80, 50, 20].forEach((level) => {
      ctx.strokeStyle = "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(level));
      ctx.lineTo(width - PAD.right, scale(level));
      ctx.stroke();
    });

    drawLine(ctx, k, barX, scale, "#00d9a3", 1.5);
    drawLine(ctx, d, barX, scale, "#f5a623", 1);
  };

  const renderAll = () => {
    if (!props.ohlcData.length) {
      clearAll();
      return;
    }
    renderMain();
    renderVolume();
    renderRsi();
    renderMacd();
    renderStoch();
  };

  const resizeCanvas = (canvas, element) => {
    if (!canvas || !element) return;
    const dpr = getDpr();
    canvas.width = Math.max(1, element.offsetWidth * dpr);
    canvas.height = Math.max(1, element.offsetHeight * dpr);
    canvas.style.width = `${element.offsetWidth}px`;
    canvas.style.height = `${element.offsetHeight}px`;
  };

  const resizeAll = () => {
    resizeCanvas(mainCanvas.value, chartAreaRef.value);
    resizeCanvas(volumeCanvas.value, volumeCanvas.value?.parentElement);
    resizeCanvas(rsiCanvas.value, rsiCanvas.value?.parentElement);
    resizeCanvas(macdCanvas.value, macdCanvas.value?.parentElement);
    resizeCanvas(stochCanvas.value, stochCanvas.value?.parentElement);
    renderAll();
  };

  const onMouseMove = (event) => {
    if (!mainCanvas.value || !props.ohlcData.length) return;
    const rect = mainCanvas.value.getBoundingClientRect();
    const chartWidth = rect.width - PAD.left - PAD.right;
    const index = Math.floor((event.clientX - rect.left - PAD.left) / (chartWidth / props.ohlcData.length));
    if (index < 0 || index >= props.ohlcData.length) return;
    const row = props.ohlcData[index];
    emit("update-crosshair", {
      visible: true,
      date: row.date,
      open: fmtPrice(row.open),
      high: fmtPrice(row.high),
      low: fmtPrice(row.low),
      close: fmtPrice(row.close),
      volume: fmtVol(row.volume),
    });
  };

  const onMouseLeave = () => emit("hide-crosshair");

  const onChartClick = (event) => {
    if (props.activeTool !== "hline" || !mainCanvas.value || !props.ohlcData.length) return;
    const rect = mainCanvas.value.getBoundingClientRect();
    const chartHeight = rect.height - PAD.top - PAD.bottom;
    const prices = props.ohlcData.flatMap((row) => [row.high, row.low]);
    const min = Math.min(...prices) * 0.998;
    const max = Math.max(...prices) * 1.002;
    const price = max - ((event.clientY - rect.top - PAD.top) / chartHeight) * (max - min);
    emit("add-horizontal-line", price);
  };

  const handleResize = () => nextTick(() => resizeAll());

  onMounted(() => {
    nextTick(() => resizeAll());
    window.addEventListener("resize", handleResize);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("resize", handleResize);
  });

  watch(
    () => props.ohlcData,
    () => nextTick(() => renderAll()),
    { deep: true },
  );
  watch(
    () => props.drawings,
    () => nextTick(() => renderAll()),
    { deep: true },
  );
  watch(
    () => props.activeInd,
    () => nextTick(() => renderAll()),
    { deep: true },
  );
  watch(
    () => [props.activePanels.rsi, props.activePanels.macd, props.activePanels.stoch],
    () => nextTick(() => resizeAll()),
  );

  return {
    onMouseMove,
    onMouseLeave,
    onChartClick,
  };
}

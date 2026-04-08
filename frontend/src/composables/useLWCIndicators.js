import {
  calcADX,
  calcAroon,
  calcBB,
  calcBBPercent,
  calcBBWidth,
  calcCCIValues,
  calcCMF,
  calcDonchianChannels,
  calcEMA,
  calcIchimoku,
  calcKeltnerChannels,
  calcMACD,
  calcMA,
  calcMFI,
  calcOBV,
  calcParabolicSAR,
  calcROC,
  calcRSI,
  calcStoch,
  calcSuperTrend,
  calcTrix,
  calcVWAP,
  calcWilliamsR,
  calcATRSeries,
} from "../utils/indicatorUtils";

const PANEL_ORDER = [
  "rsi",
  "aroon",
  "trix",
  "williamsr",
  "mfi",
  "roc",
  "bbPercent",
  "bbWidth",
  "macd",
  "stoch",
  "atr",
  "cci",
  "obv",
  "adx",
  "cmf",
];

function withWhitespace(rows, values, formatter = (value) => value) {
  return rows.map((row, index) => {
    const value = values[index];
    if (value == null || Number.isNaN(Number(value))) {
      return { time: row.time };
    }
    return {
      time: row.time,
      value: formatter(value),
    };
  });
}

function withHistogramWhitespace(rows, values, colorResolver) {
  return rows.map((row, index) => {
    const value = values[index];
    if (value == null || Number.isNaN(Number(value))) {
      return { time: row.time };
    }
    return {
      time: row.time,
      value: Number(value),
      color: colorResolver ? colorResolver(value, row, index) : undefined,
    };
  });
}

function addLineSeries(target, key, values, options = {}) {
  target.push({
    key,
    type: "line",
    options,
    data: withWhitespace(options.rows, values, (value) => Number(value)),
  });
}

function addHistogramSeries(target, key, values, options = {}) {
  target.push({
    key,
    type: "histogram",
    options,
    data: withHistogramWhitespace(options.rows, values, options.colorResolver),
  });
}

function buildMainOverlays(rows, activeInd, settings) {
  const overlays = [];
  if (!rows.length) return overlays;

  if (activeInd.cycleMa) {
    [
      [5, "#7be7ff"],
      [10, "#8dc1ff"],
      [20, "#ffd166"],
      [60, "#9b6dff"],
      [120, "#ff8c42"],
      [240, "#ff6b6b"],
    ].forEach(([period, color]) => {
      addLineSeries(overlays, `cycle-ma-${period}`, calcMA(rows, period), {
        rows,
        color,
        lineWidth: period >= 120 ? 1.2 : 1.05,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    });
  }

  if (activeInd.ma20) {
    addLineSeries(overlays, "ma20", calcMA(rows, settings.ma20Period), {
      rows,
      color: "#3b8bff",
      lineWidth: 1.5,
      priceLineVisible: false,
    });
  }
  if (activeInd.ma50) {
    addLineSeries(overlays, "ma50", calcMA(rows, settings.ma50Period), {
      rows,
      color: "#f5a623",
      lineWidth: 1.5,
      priceLineVisible: false,
    });
  }
  if (activeInd.ma200) {
    addLineSeries(overlays, "ma200", calcMA(rows, settings.ma200Period), {
      rows,
      color: "#9b6dff",
      lineWidth: 1.4,
      priceLineVisible: false,
    });
  }
  if (activeInd.ema12) {
    addLineSeries(overlays, "ema12", calcEMA(rows, settings.emaPeriod), {
      rows,
      color: "#00d4ff",
      lineWidth: 1.1,
      priceLineVisible: false,
    });
  }
  if (activeInd.vwap) {
    addLineSeries(overlays, "vwap", calcVWAP(rows), {
      rows,
      color: "#ff8c42",
      lineWidth: 1.1,
      lineStyle: 2,
      priceLineVisible: false,
    });
  }

  if (activeInd.bb) {
    const bb = calcBB(rows, settings.bbPeriod, settings.bbMultiplier);
    addLineSeries(overlays, "bb-upper", bb.map((item) => item.u), {
      rows,
      color: "#ffd166",
      lineWidth: 0.9,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "bb-lower", bb.map((item) => item.l), {
      rows,
      color: "#ffd166",
      lineWidth: 0.9,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "bb-middle", bb.map((item) => item.m), {
      rows,
      color: "rgba(255,209,102,0.65)",
      lineWidth: 0.8,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  if (activeInd.psar) {
    addLineSeries(overlays, "psar", calcParabolicSAR(rows, settings.psarStep, settings.psarMax), {
      rows,
      color: "#00d9a3",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
  }

  if (activeInd.keltner) {
    const keltner = calcKeltnerChannels(rows, settings.kcPeriod, settings.kcMultiplier);
    addLineSeries(overlays, "kc-upper", keltner.map((item) => item.u), {
      rows,
      color: "#7be7ff",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "kc-lower", keltner.map((item) => item.l), {
      rows,
      color: "#7be7ff",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "kc-middle", keltner.map((item) => item.m), {
      rows,
      color: "rgba(123,231,255,0.68)",
      lineWidth: 0.8,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  if (activeInd.donchian) {
    const donchian = calcDonchianChannels(rows, settings.donchianPeriod);
    addLineSeries(overlays, "donchian-upper", donchian.map((item) => item.u), {
      rows,
      color: "#9b6dff",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "donchian-lower", donchian.map((item) => item.l), {
      rows,
      color: "#9b6dff",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "donchian-middle", donchian.map((item) => item.m), {
      rows,
      color: "rgba(155,109,255,0.6)",
      lineWidth: 0.8,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  if (activeInd.ichimoku) {
    const ichimoku = calcIchimoku(
      rows,
      settings.ichimokuConversion,
      settings.ichimokuBase,
      settings.ichimokuSpanB,
      settings.ichimokuDisplacement,
    );
    addLineSeries(overlays, "ichimoku-conversion", ichimoku.conversion, {
      rows,
      color: "#7be7ff",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "ichimoku-base", ichimoku.base, {
      rows,
      color: "#9b6dff",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "ichimoku-span-a", ichimoku.spanA, {
      rows,
      color: "rgba(0,217,163,0.8)",
      lineWidth: 0.9,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "ichimoku-span-b", ichimoku.spanB, {
      rows,
      color: "rgba(255,77,106,0.8)",
      lineWidth: 0.9,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    addLineSeries(overlays, "ichimoku-lagging", ichimoku.lagging, {
      rows,
      color: "rgba(255,209,102,0.6)",
      lineWidth: 0.8,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  if (activeInd.supertrend) {
    const superTrend = calcSuperTrend(rows, settings.supertrendPeriod, settings.supertrendMultiplier);
    addLineSeries(
      overlays,
      "supertrend-up",
      superTrend.line.map((value, index) => (superTrend.trend[index] === 1 ? value : null)),
      {
        rows,
        color: "#00d9a3",
        lineWidth: 1.7,
        priceLineVisible: false,
        lastValueVisible: false,
      },
    );
    addLineSeries(
      overlays,
      "supertrend-down",
      superTrend.line.map((value, index) => (superTrend.trend[index] === -1 ? value : null)),
      {
        rows,
        color: "#ff4d6a",
        lineWidth: 1.7,
        priceLineVisible: false,
        lastValueVisible: false,
      },
    );
  }

  return overlays;
}

function buildPanels(rows, activePanels, settings) {
  const panels = [];
  if (!rows.length) return panels;

  const addPanel = (panel) => {
    if (!panel || !panel.key) return;
    panels.push(panel);
  };

  PANEL_ORDER.forEach((panelKey) => {
    if (!activePanels[panelKey]) return;

    if (panelKey === "rsi") {
      addPanel({
        key: "rsi",
        title: `RSI(${settings.rsiPeriod})`,
        priceLines: [
          { price: 70, color: "rgba(255,77,106,0.55)", lineStyle: 2 },
          { price: 50, color: "rgba(152,167,183,0.35)", lineStyle: 2 },
          { price: 30, color: "rgba(0,217,163,0.55)", lineStyle: 2 },
        ],
        series: [
          {
            key: "rsi-line",
            type: "line",
            options: { color: "#9b6dff", lineWidth: 1.6, priceLineVisible: false },
            data: withWhitespace(rows, calcRSI(rows, settings.rsiPeriod), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "aroon") {
      const aroon = calcAroon(rows, settings.aroonPeriod);
      addPanel({
        key: "aroon",
        title: `Aroon(${settings.aroonPeriod})`,
        priceLines: [{ price: 50, color: "rgba(152,167,183,0.35)", lineStyle: 2 }],
        series: [
          {
            key: "aroon-up",
            type: "line",
            options: { color: "#00d9a3", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, aroon.map((item) => item.up), Number),
          },
          {
            key: "aroon-down",
            type: "line",
            options: { color: "#ff4d6a", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, aroon.map((item) => item.down), Number),
          },
          {
            key: "aroon-osc",
            type: "line",
            options: { color: "#7be7ff", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false },
            data: withWhitespace(rows, aroon.map((item) => item.osc), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "trix") {
      const trix = calcTrix(rows, settings.trixPeriod, settings.trixSignal);
      addPanel({
        key: "trix",
        title: `TRIX(${settings.trixPeriod},${settings.trixSignal})`,
        priceLines: [{ price: 0, color: "rgba(152,167,183,0.35)", lineStyle: 2 }],
        series: [
          {
            key: "trix-line",
            type: "line",
            options: { color: "#8dc1ff", lineWidth: 1.5, priceLineVisible: false },
            data: withWhitespace(rows, trix.trix, Number),
          },
          {
            key: "trix-signal",
            type: "line",
            options: { color: "#ff8c42", lineWidth: 1.2, priceLineVisible: false },
            data: withWhitespace(rows, trix.signal, Number),
          },
          {
            key: "trix-hist",
            type: "histogram",
            options: { priceLineVisible: false, lastValueVisible: false, base: 0 },
            data: withHistogramWhitespace(rows, trix.hist, (value) =>
              value >= 0 ? "rgba(0,217,163,0.65)" : "rgba(255,77,106,0.65)"),
          },
        ],
      });
      return;
    }

    if (panelKey === "williamsr") {
      addPanel({
        key: "williamsr",
        title: `Williams %R(${settings.williamsrPeriod})`,
        priceLines: [
          { price: -20, color: "rgba(255,77,106,0.55)", lineStyle: 2 },
          { price: -50, color: "rgba(152,167,183,0.35)", lineStyle: 2 },
          { price: -80, color: "rgba(0,217,163,0.55)", lineStyle: 2 },
        ],
        series: [
          {
            key: "williamsr-line",
            type: "line",
            options: { color: "#ff8c42", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcWilliamsR(rows, settings.williamsrPeriod), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "mfi") {
      addPanel({
        key: "mfi",
        title: `MFI(${settings.mfiPeriod})`,
        priceLines: [
          { price: 80, color: "rgba(255,77,106,0.55)", lineStyle: 2 },
          { price: 50, color: "rgba(152,167,183,0.35)", lineStyle: 2 },
          { price: 20, color: "rgba(0,217,163,0.55)", lineStyle: 2 },
        ],
        series: [
          {
            key: "mfi-line",
            type: "line",
            options: { color: "#ffd166", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcMFI(rows, settings.mfiPeriod), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "roc") {
      addPanel({
        key: "roc",
        title: `ROC(${settings.rocPeriod})`,
        priceLines: [{ price: 0, color: "rgba(152,167,183,0.35)", lineStyle: 2 }],
        series: [
          {
            key: "roc-line",
            type: "line",
            options: { color: "#7be7ff", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcROC(rows, settings.rocPeriod), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "bbPercent") {
      addPanel({
        key: "bbPercent",
        title: `BB %B(${settings.bbPeriod})`,
        priceLines: [
          { price: 100, color: "rgba(255,77,106,0.55)", lineStyle: 2 },
          { price: 50, color: "rgba(152,167,183,0.35)", lineStyle: 2 },
          { price: 0, color: "rgba(0,217,163,0.55)", lineStyle: 2 },
        ],
        series: [
          {
            key: "bbpercent-line",
            type: "line",
            options: { color: "#ffd166", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcBBPercent(rows, settings.bbPeriod, settings.bbMultiplier), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "bbWidth") {
      addPanel({
        key: "bbWidth",
        title: `BB Width(${settings.bbPeriod})`,
        priceLines: [{ price: 0, color: "rgba(152,167,183,0.35)", lineStyle: 2 }],
        series: [
          {
            key: "bbwidth-line",
            type: "line",
            options: { color: "#9b6dff", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcBBWidth(rows, settings.bbPeriod, settings.bbMultiplier), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "macd") {
      const macd = calcMACD(rows, settings.macdFast, settings.macdSlow, settings.macdSignal);
      addPanel({
        key: "macd",
        title: `MACD(${settings.macdFast},${settings.macdSlow},${settings.macdSignal})`,
        priceLines: [{ price: 0, color: "rgba(152,167,183,0.35)", lineStyle: 2 }],
        series: [
          {
            key: "macd-hist",
            type: "histogram",
            options: { priceLineVisible: false, lastValueVisible: false, base: 0 },
            data: withHistogramWhitespace(rows, macd.hist, (value) =>
              value >= 0 ? "rgba(0,217,163,0.72)" : "rgba(255,77,106,0.72)"),
          },
          {
            key: "macd-line",
            type: "line",
            options: { color: "#00d4ff", lineWidth: 1.5, priceLineVisible: false },
            data: withWhitespace(rows, macd.macd, Number),
          },
          {
            key: "macd-signal",
            type: "line",
            options: { color: "#ff8c42", lineWidth: 1.2, priceLineVisible: false },
            data: withWhitespace(rows, macd.signal, Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "stoch") {
      const stoch = calcStoch(rows, settings.stochK, settings.stochD);
      addPanel({
        key: "stoch",
        title: `KD Stoch(${settings.stochK},${settings.stochD})`,
        priceLines: [
          { price: 80, color: "rgba(255,77,106,0.55)", lineStyle: 2 },
          { price: 50, color: "rgba(152,167,183,0.35)", lineStyle: 2 },
          { price: 20, color: "rgba(0,217,163,0.55)", lineStyle: 2 },
        ],
        series: [
          {
            key: "stoch-k",
            type: "line",
            options: { color: "#00d4ff", lineWidth: 1.5, priceLineVisible: false },
            data: withWhitespace(rows, stoch.k, Number),
          },
          {
            key: "stoch-d",
            type: "line",
            options: { color: "#ff8c42", lineWidth: 1.2, priceLineVisible: false },
            data: withWhitespace(rows, stoch.d, Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "atr") {
      addPanel({
        key: "atr",
        title: `ATR(${settings.atrPeriod})`,
        priceLines: [{ price: 0, color: "rgba(152,167,183,0.35)", lineStyle: 2 }],
        series: [
          {
            key: "atr-line",
            type: "line",
            options: { color: "#ffd166", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcATRSeries(rows, settings.atrPeriod), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "cci") {
      addPanel({
        key: "cci",
        title: `CCI(${settings.cciPeriod})`,
        priceLines: [
          { price: 100, color: "rgba(255,77,106,0.55)", lineStyle: 2 },
          { price: 0, color: "rgba(152,167,183,0.35)", lineStyle: 2 },
          { price: -100, color: "rgba(0,217,163,0.55)", lineStyle: 2 },
        ],
        series: [
          {
            key: "cci-line",
            type: "line",
            options: { color: "#9b6dff", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcCCIValues(rows, settings.cciPeriod), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "obv") {
      addPanel({
        key: "obv",
        title: "OBV",
        priceLines: [],
        series: [
          {
            key: "obv-line",
            type: "line",
            options: { color: "#7be7ff", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcOBV(rows), Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "adx") {
      const adx = calcADX(rows, settings.adxPeriod);
      addPanel({
        key: "adx",
        title: `ADX(${settings.adxPeriod})`,
        priceLines: [{ price: 25, color: "rgba(152,167,183,0.35)", lineStyle: 2 }],
        series: [
          {
            key: "adx-plus",
            type: "line",
            options: { color: "#00d9a3", lineWidth: 1.3, priceLineVisible: false },
            data: withWhitespace(rows, adx.plusDI, Number),
          },
          {
            key: "adx-minus",
            type: "line",
            options: { color: "#ff4d6a", lineWidth: 1.3, priceLineVisible: false },
            data: withWhitespace(rows, adx.minusDI, Number),
          },
          {
            key: "adx-line",
            type: "line",
            options: { color: "#ffd166", lineWidth: 1.5, priceLineVisible: false },
            data: withWhitespace(rows, adx.adx, Number),
          },
        ],
      });
      return;
    }

    if (panelKey === "cmf") {
      addPanel({
        key: "cmf",
        title: `CMF(${settings.cmfPeriod})`,
        priceLines: [{ price: 0, color: "rgba(152,167,183,0.35)", lineStyle: 2 }],
        series: [
          {
            key: "cmf-line",
            type: "line",
            options: { color: "#7be7ff", lineWidth: 1.4, priceLineVisible: false },
            data: withWhitespace(rows, calcCMF(rows, settings.cmfPeriod), Number),
          },
        ],
      });
    }
  });

  return panels;
}

export function buildLWCIndicatorModel({
  rows = [],
  activeInd = {},
  activePanels = {},
  settings = {},
}) {
  return {
    overlays: buildMainOverlays(rows, activeInd, settings),
    panels: buildPanels(rows, activePanels, settings),
  };
}

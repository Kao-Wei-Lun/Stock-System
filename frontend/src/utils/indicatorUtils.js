const EMPTY = "—";

export const DEFAULT_INDICATOR_SETTINGS = {
  ma20Period: 20,
  ma50Period: 50,
  ma200Period: 200,
  emaPeriod: 12,
  bbPeriod: 20,
  bbMultiplier: 2,
  kcPeriod: 20,
  kcMultiplier: 2,
  donchianPeriod: 20,
  rsiPeriod: 14,
  williamsrPeriod: 14,
  mfiPeriod: 14,
  rocPeriod: 12,
  macdFast: 12,
  macdSlow: 26,
  macdSignal: 9,
  stochK: 14,
  stochD: 3,
  volumeMaPeriod: 20,
  atrPeriod: 14,
  cciPeriod: 20,
  adxPeriod: 14,
  cmfPeriod: 20,
  ichimokuConversion: 9,
  ichimokuBase: 26,
  ichimokuSpanB: 52,
  ichimokuDisplacement: 26,
  supertrendPeriod: 10,
  supertrendMultiplier: 3,
};

const clampInteger = (value, min, max, fallback) => {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(Math.max(parsed, min), max);
};

const clampNumber = (value, min, max, fallback) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(Math.max(parsed, min), max);
};

export function normalizeIndicatorSettings(input = {}) {
  const merged = { ...DEFAULT_INDICATOR_SETTINGS, ...(input || {}) };
  const normalized = {
    ma20Period: clampInteger(merged.ma20Period, 2, 400, DEFAULT_INDICATOR_SETTINGS.ma20Period),
    ma50Period: clampInteger(merged.ma50Period, 2, 600, DEFAULT_INDICATOR_SETTINGS.ma50Period),
    ma200Period: clampInteger(merged.ma200Period, 2, 1200, DEFAULT_INDICATOR_SETTINGS.ma200Period),
    emaPeriod: clampInteger(merged.emaPeriod, 2, 400, DEFAULT_INDICATOR_SETTINGS.emaPeriod),
    bbPeriod: clampInteger(merged.bbPeriod, 5, 300, DEFAULT_INDICATOR_SETTINGS.bbPeriod),
    bbMultiplier: clampNumber(merged.bbMultiplier, 0.5, 6, DEFAULT_INDICATOR_SETTINGS.bbMultiplier),
    kcPeriod: clampInteger(merged.kcPeriod, 2, 300, DEFAULT_INDICATOR_SETTINGS.kcPeriod),
    kcMultiplier: clampNumber(merged.kcMultiplier, 0.5, 6, DEFAULT_INDICATOR_SETTINGS.kcMultiplier),
    donchianPeriod: clampInteger(merged.donchianPeriod, 2, 300, DEFAULT_INDICATOR_SETTINGS.donchianPeriod),
    rsiPeriod: clampInteger(merged.rsiPeriod, 2, 100, DEFAULT_INDICATOR_SETTINGS.rsiPeriod),
    williamsrPeriod: clampInteger(merged.williamsrPeriod, 2, 100, DEFAULT_INDICATOR_SETTINGS.williamsrPeriod),
    mfiPeriod: clampInteger(merged.mfiPeriod, 2, 100, DEFAULT_INDICATOR_SETTINGS.mfiPeriod),
    rocPeriod: clampInteger(merged.rocPeriod, 1, 120, DEFAULT_INDICATOR_SETTINGS.rocPeriod),
    macdFast: clampInteger(merged.macdFast, 2, 60, DEFAULT_INDICATOR_SETTINGS.macdFast),
    macdSlow: clampInteger(merged.macdSlow, 3, 120, DEFAULT_INDICATOR_SETTINGS.macdSlow),
    macdSignal: clampInteger(merged.macdSignal, 2, 60, DEFAULT_INDICATOR_SETTINGS.macdSignal),
    stochK: clampInteger(merged.stochK, 3, 100, DEFAULT_INDICATOR_SETTINGS.stochK),
    stochD: clampInteger(merged.stochD, 2, 20, DEFAULT_INDICATOR_SETTINGS.stochD),
    volumeMaPeriod: clampInteger(merged.volumeMaPeriod, 2, 200, DEFAULT_INDICATOR_SETTINGS.volumeMaPeriod),
    atrPeriod: clampInteger(merged.atrPeriod, 2, 120, DEFAULT_INDICATOR_SETTINGS.atrPeriod),
    cciPeriod: clampInteger(merged.cciPeriod, 3, 120, DEFAULT_INDICATOR_SETTINGS.cciPeriod),
    adxPeriod: clampInteger(merged.adxPeriod, 2, 120, DEFAULT_INDICATOR_SETTINGS.adxPeriod),
    cmfPeriod: clampInteger(merged.cmfPeriod, 2, 120, DEFAULT_INDICATOR_SETTINGS.cmfPeriod),
    ichimokuConversion: clampInteger(merged.ichimokuConversion, 2, 60, DEFAULT_INDICATOR_SETTINGS.ichimokuConversion),
    ichimokuBase: clampInteger(merged.ichimokuBase, 3, 120, DEFAULT_INDICATOR_SETTINGS.ichimokuBase),
    ichimokuSpanB: clampInteger(merged.ichimokuSpanB, 4, 240, DEFAULT_INDICATOR_SETTINGS.ichimokuSpanB),
    ichimokuDisplacement: clampInteger(merged.ichimokuDisplacement, 1, 120, DEFAULT_INDICATOR_SETTINGS.ichimokuDisplacement),
    supertrendPeriod: clampInteger(merged.supertrendPeriod, 2, 120, DEFAULT_INDICATOR_SETTINGS.supertrendPeriod),
    supertrendMultiplier: clampNumber(merged.supertrendMultiplier, 0.5, 10, DEFAULT_INDICATOR_SETTINGS.supertrendMultiplier),
  };

  if (normalized.macdSlow <= normalized.macdFast) {
    normalized.macdSlow = Math.min(normalized.macdFast + 1, 120);
  }
  if (normalized.ichimokuBase <= normalized.ichimokuConversion) {
    normalized.ichimokuBase = Math.min(normalized.ichimokuConversion + 1, 120);
  }
  if (normalized.ichimokuSpanB <= normalized.ichimokuBase) {
    normalized.ichimokuSpanB = Math.min(normalized.ichimokuBase + 1, 240);
  }

  return normalized;
}

export const calcMA = (data, n) =>
  data.map((_, index) =>
    index < n - 1
      ? null
      : Number(
          (
            data
              .slice(index - n + 1, index + 1)
              .reduce((accumulator, row) => accumulator + row.close, 0) / n
          ).toFixed(4),
        ),
  );

export const calcEMA = (data, n) => {
  const k = 2 / (n + 1);
  const ema = [];
  data.forEach((row, index) => {
    ema.push(index === 0 ? row.close : Number((row.close * k + ema[index - 1] * (1 - k)).toFixed(4)));
  });
  return ema;
};

export const calcRSI = (data, n = 14) => {
  const gains = [];
  const losses = [];
  const rsi = [null];

  for (let index = 1; index < data.length; index += 1) {
    const delta = data[index].close - data[index - 1].close;
    gains.push(delta > 0 ? delta : 0);
    losses.push(delta < 0 ? -delta : 0);
  }

  for (let index = 0; index < gains.length; index += 1) {
    if (index < n - 1) {
      rsi.push(null);
      continue;
    }
    const avgGain = gains.slice(index - n + 1, index + 1).reduce((sum, value) => sum + value, 0) / n;
    const avgLoss = losses.slice(index - n + 1, index + 1).reduce((sum, value) => sum + value, 0) / n;
    rsi.push(avgLoss === 0 ? 100 : Number((100 - 100 / (1 + avgGain / avgLoss)).toFixed(2)));
  }

  return rsi;
};

export const calcMACD = (data, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) => {
  const emaFast = calcEMA(data, fastPeriod);
  const emaSlow = calcEMA(data, slowPeriod);
  const macd = emaFast.map((value, index) => Number((value - emaSlow[index]).toFixed(4)));
  const signal = calcEMA(macd.map((value) => ({ close: value || 0 })), signalPeriod);
  const hist = macd.map((value, index) => Number((value - signal[index]).toFixed(4)));
  return { macd, signal, hist };
};

export const calcBB = (data, n = 20, multiplier = 2) =>
  data.map((_, index) => {
    if (index < n - 1) {
      return { u: null, m: null, l: null };
    }
    const slice = data.slice(index - n + 1, index + 1);
    const mean = slice.reduce((sum, row) => sum + row.close, 0) / slice.length;
    const std = Math.sqrt(slice.reduce((sum, row) => sum + (row.close - mean) ** 2, 0) / slice.length);
    return {
      u: Number((mean + multiplier * std).toFixed(4)),
      m: Number(mean.toFixed(4)),
      l: Number((mean - multiplier * std).toFixed(4)),
    };
  });

export const calcKeltnerChannels = (data, n = 20, multiplier = 2) => {
  const basis = calcEMA(data, n);
  const atr = calcATRSeries(data, n);
  return data.map((_, index) => {
    const middle = basis[index];
    const atrValue = atr[index];
    if (middle == null || atrValue == null) {
      return { u: null, m: null, l: null };
    }
    return {
      u: Number((middle + atrValue * multiplier).toFixed(4)),
      m: Number(middle.toFixed(4)),
      l: Number((middle - atrValue * multiplier).toFixed(4)),
    };
  });
};

export const calcDonchianChannels = (data, n = 20) =>
  data.map((_, index) => {
    if (index < n - 1) {
      return { u: null, m: null, l: null };
    }
    const slice = data.slice(index - n + 1, index + 1);
    const upper = Math.max(...slice.map((row) => row.high));
    const lower = Math.min(...slice.map((row) => row.low));
    return {
      u: Number(upper.toFixed(4)),
      m: Number((((upper + lower) / 2)).toFixed(4)),
      l: Number(lower.toFixed(4)),
    };
  });

export const calcStoch = (data, kPeriod = 14, dPeriod = 3) => {
  const kValues = [];
  const dValues = [];

  data.forEach((row, index) => {
    if (index < kPeriod - 1) {
      kValues.push(null);
      return;
    }
    const slice = data.slice(index - kPeriod + 1, index + 1);
    const high = Math.max(...slice.map((item) => item.high));
    const low = Math.min(...slice.map((item) => item.low));
    kValues.push(high === low ? 50 : Number((((row.close - low) / (high - low)) * 100).toFixed(2)));
  });

  kValues.forEach((value, index) => {
    if (index < dPeriod - 1) {
      dValues.push(null);
      return;
    }
    const slice = kValues.slice(index - dPeriod + 1, index + 1).filter((item) => item != null);
    dValues.push(slice.length ? Number((slice.reduce((sum, item) => sum + item, 0) / slice.length).toFixed(2)) : null);
  });

  return { k: kValues, d: dValues };
};

export const calcVWAP = (data) => {
  let cumulativeTpv = 0;
  let cumulativeVolume = 0;
  return data.map((row) => {
    const typicalPrice = (row.high + row.low + row.close) / 3;
    cumulativeTpv += typicalPrice * row.volume;
    cumulativeVolume += row.volume;
    return cumulativeVolume ? Number((cumulativeTpv / cumulativeVolume).toFixed(4)) : null;
  });
};

export const calcWilliamsR = (data, n = 14) =>
  data.map((row, index) => {
    if (index < n - 1) return null;
    const slice = data.slice(index - n + 1, index + 1);
    const high = Math.max(...slice.map((item) => item.high));
    const low = Math.min(...slice.map((item) => item.low));
    if (high === low) return 0;
    return Number((((high - row.close) / (high - low)) * -100).toFixed(2));
  });

export const calcMFI = (data, n = 14) => {
  const positive = Array(data.length).fill(null);
  const negative = Array(data.length).fill(null);
  const result = Array(data.length).fill(null);

  for (let index = 1; index < data.length; index += 1) {
    const typical = (data[index].high + data[index].low + data[index].close) / 3;
    const previousTypical = (data[index - 1].high + data[index - 1].low + data[index - 1].close) / 3;
    const rawFlow = typical * Number(data[index].volume || 0);
    if (typical > previousTypical) {
      positive[index] = rawFlow;
      negative[index] = 0;
    } else if (typical < previousTypical) {
      positive[index] = 0;
      negative[index] = rawFlow;
    } else {
      positive[index] = 0;
      negative[index] = 0;
    }
  }

  for (let index = 0; index < data.length; index += 1) {
    if (index < n) continue;
    const positiveFlow = positive.slice(index - n + 1, index + 1).reduce((sum, value) => sum + (value || 0), 0);
    const negativeFlow = negative.slice(index - n + 1, index + 1).reduce((sum, value) => sum + (value || 0), 0);
    if (negativeFlow === 0) {
      result[index] = 100;
      continue;
    }
    const moneyRatio = positiveFlow / negativeFlow;
    result[index] = Number((100 - 100 / (1 + moneyRatio)).toFixed(2));
  }

  return result;
};

export const calcROC = (data, n = 12) =>
  data.map((row, index) => {
    if (index < n) return null;
    const base = data[index - n].close;
    if (!base) return null;
    return Number((((row.close - base) / base) * 100).toFixed(2));
  });

export const calcATRSeries = (data, n = 14) => {
  const atr = [];
  let rollingTrSum = 0;

  data.forEach((row, index) => {
    const previous = data[index - 1] || row;
    const trueRange = Math.max(
      row.high - row.low,
      Math.abs(row.high - previous.close),
      Math.abs(row.low - previous.close),
    );

    if (index < n) {
      rollingTrSum += trueRange;
      atr.push(Number((rollingTrSum / (index + 1)).toFixed(4)));
      return;
    }

    const previousAtr = atr[index - 1] ?? trueRange;
    atr.push(Number((((previousAtr * (n - 1)) + trueRange) / n).toFixed(4)));
  });

  return atr;
};

export const calcCCIValues = (data, n = 20) =>
  data.map((_, index) => {
    if (index < n - 1) return null;
    const slice = data.slice(index - n + 1, index + 1);
    const typicalPrices = slice.map((row) => (row.high + row.low + row.close) / 3);
    const mean = typicalPrices.reduce((sum, value) => sum + value, 0) / n;
    const meanDeviation = typicalPrices.reduce((sum, value) => sum + Math.abs(value - mean), 0) / n;
    return meanDeviation
      ? Number(((typicalPrices[typicalPrices.length - 1] - mean) / (0.015 * meanDeviation)).toFixed(2))
      : null;
  });

export const calcATR = (data, n = 14) => calcATRSeries(data, n).at(-1) ?? 0;

export const calcCCI = (data, n = 20) => calcCCIValues(data, n).at(-1) ?? null;

export const calcOBV = (data) => {
  if (!data.length) return [];
  const obv = [0];
  for (let index = 1; index < data.length; index += 1) {
    const previous = obv[index - 1];
    const volume = Number(data[index].volume || 0);
    if (data[index].close > data[index - 1].close) obv.push(previous + volume);
    else if (data[index].close < data[index - 1].close) obv.push(previous - volume);
    else obv.push(previous);
  }
  return obv;
};

export const calcCMF = (data, n = 20) =>
  data.map((row, index) => {
    if (index < n - 1) return null;
    const slice = data.slice(index - n + 1, index + 1);
    const moneyFlowVolume = slice.reduce((sum, item) => {
      const highLowRange = item.high - item.low;
      const multiplier = highLowRange === 0
        ? 0
        : (((item.close - item.low) - (item.high - item.close)) / highLowRange);
      return sum + multiplier * Number(item.volume || 0);
    }, 0);
    const totalVolume = slice.reduce((sum, item) => sum + Number(item.volume || 0), 0);
    return totalVolume ? Number((moneyFlowVolume / totalVolume).toFixed(4)) : null;
  });

export const calcADX = (data, n = 14) => {
  const plusDI = Array(data.length).fill(null);
  const minusDI = Array(data.length).fill(null);
  const adx = Array(data.length).fill(null);
  const dx = Array(data.length).fill(null);

  if (data.length < 2) return { plusDI, minusDI, adx };

  let smoothedTr = 0;
  let smoothedPlusDm = 0;
  let smoothedMinusDm = 0;
  let previousAdx = null;

  for (let index = 1; index < data.length; index += 1) {
    const current = data[index];
    const previous = data[index - 1];
    const highMove = current.high - previous.high;
    const lowMove = previous.low - current.low;
    const plusDm = highMove > lowMove && highMove > 0 ? highMove : 0;
    const minusDm = lowMove > highMove && lowMove > 0 ? lowMove : 0;
    const trueRange = Math.max(
      current.high - current.low,
      Math.abs(current.high - previous.close),
      Math.abs(current.low - previous.close),
    );

    if (index <= n) {
      smoothedTr += trueRange;
      smoothedPlusDm += plusDm;
      smoothedMinusDm += minusDm;
    } else {
      smoothedTr = smoothedTr - (smoothedTr / n) + trueRange;
      smoothedPlusDm = smoothedPlusDm - (smoothedPlusDm / n) + plusDm;
      smoothedMinusDm = smoothedMinusDm - (smoothedMinusDm / n) + minusDm;
    }

    if (index < n) continue;

    const currentPlusDi = smoothedTr ? (smoothedPlusDm / smoothedTr) * 100 : 0;
    const currentMinusDi = smoothedTr ? (smoothedMinusDm / smoothedTr) * 100 : 0;
    plusDI[index] = Number(currentPlusDi.toFixed(2));
    minusDI[index] = Number(currentMinusDi.toFixed(2));

    const denominator = currentPlusDi + currentMinusDi;
    const currentDx = denominator ? (Math.abs(currentPlusDi - currentMinusDi) / denominator) * 100 : 0;
    dx[index] = currentDx;

    if (index === n * 2 - 2) {
      const seed = dx.slice(n, index + 1).filter((value) => value != null);
      previousAdx = seed.length ? seed.reduce((sum, value) => sum + value, 0) / seed.length : currentDx;
      adx[index] = Number(previousAdx.toFixed(2));
      continue;
    }

    if (index > n * 2 - 2) {
      previousAdx = previousAdx == null ? currentDx : ((previousAdx * (n - 1)) + currentDx) / n;
      adx[index] = Number(previousAdx.toFixed(2));
    }
  }

  return { plusDI, minusDI, adx };
};

export const calcIchimoku = (
  data,
  conversionPeriod = 9,
  basePeriod = 26,
  spanBPeriod = 52,
  displacement = 26,
) => {
  const conversion = Array(data.length).fill(null);
  const base = Array(data.length).fill(null);
  const spanA = Array(data.length).fill(null);
  const spanB = Array(data.length).fill(null);
  const lagging = Array(data.length).fill(null);

  data.forEach((row, index) => {
    if (index >= conversionPeriod - 1) {
      const slice = data.slice(index - conversionPeriod + 1, index + 1);
      const high = Math.max(...slice.map((item) => item.high));
      const low = Math.min(...slice.map((item) => item.low));
      conversion[index] = Number(((high + low) / 2).toFixed(4));
    }

    if (index >= basePeriod - 1) {
      const slice = data.slice(index - basePeriod + 1, index + 1);
      const high = Math.max(...slice.map((item) => item.high));
      const low = Math.min(...slice.map((item) => item.low));
      base[index] = Number(((high + low) / 2).toFixed(4));
    }

    if (conversion[index] != null && base[index] != null && index + displacement < data.length) {
      spanA[index + displacement] = Number(((conversion[index] + base[index]) / 2).toFixed(4));
    }

    if (index >= spanBPeriod - 1 && index + displacement < data.length) {
      const slice = data.slice(index - spanBPeriod + 1, index + 1);
      const high = Math.max(...slice.map((item) => item.high));
      const low = Math.min(...slice.map((item) => item.low));
      spanB[index + displacement] = Number(((high + low) / 2).toFixed(4));
    }

    if (index - displacement >= 0) {
      lagging[index - displacement] = row.close;
    }
  });

  return { conversion, base, spanA, spanB, lagging };
};

export const calcSuperTrend = (data, period = 10, multiplier = 3) => {
  const atr = calcATRSeries(data, period);
  const upperBand = Array(data.length).fill(null);
  const lowerBand = Array(data.length).fill(null);
  const line = Array(data.length).fill(null);
  const trend = Array(data.length).fill(null);

  let finalUpper = null;
  let finalLower = null;
  let previousLine = null;

  data.forEach((row, index) => {
    const atrValue = atr[index];
    if (atrValue == null) return;

    const hl2 = (row.high + row.low) / 2;
    const basicUpper = hl2 + multiplier * atrValue;
    const basicLower = hl2 - multiplier * atrValue;

    if (index === 0 || finalUpper == null || finalLower == null) {
      finalUpper = basicUpper;
      finalLower = basicLower;
      line[index] = row.close >= basicLower ? basicLower : basicUpper;
      trend[index] = row.close >= basicLower ? 1 : -1;
      upperBand[index] = Number(finalUpper.toFixed(4));
      lowerBand[index] = Number(finalLower.toFixed(4));
      previousLine = line[index];
      return;
    }

    finalUpper = basicUpper < finalUpper || data[index - 1].close > finalUpper ? basicUpper : finalUpper;
    finalLower = basicLower > finalLower || data[index - 1].close < finalLower ? basicLower : finalLower;

    const nextTrend =
      previousLine === finalUpper
        ? (row.close > finalUpper ? 1 : -1)
        : (row.close < finalLower ? -1 : 1);

    line[index] = nextTrend === 1 ? finalLower : finalUpper;
    trend[index] = nextTrend;
    upperBand[index] = Number(finalUpper.toFixed(4));
    lowerBand[index] = Number(finalLower.toFixed(4));
    previousLine = line[index];
  });

  return { upperBand, lowerBand, line, trend };
};

const findLastDefinedValue = (series) => {
  for (let index = series.length - 1; index >= 0; index -= 1) {
    if (series[index] != null) return series[index];
  }
  return null;
};

const formatCompactNumber = (value) => {
  if (value == null) return EMPTY;
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
  return Number(value).toFixed(0);
};

export function buildIndicatorSnapshot(data, inputSettings = DEFAULT_INDICATOR_SETTINGS) {
  const settings = normalizeIndicatorSettings(inputSettings);
  if (!data.length) {
    return {
      ma20: EMPTY,
      ma50: EMPTY,
      ma200: EMPTY,
      ema12: EMPTY,
      bb: EMPTY,
      keltner: EMPTY,
      donchian: EMPTY,
      ichimoku: EMPTY,
      supertrend: EMPTY,
      rsi: EMPTY,
      rsiClass: "",
      williamsr: EMPTY,
      mfi: EMPTY,
      roc: EMPTY,
      macd: EMPTY,
      macdSignal: `Signal(${settings.macdSignal}): ${EMPTY}`,
      stoch: EMPTY,
      atr: EMPTY,
      cci: EMPTY,
      obv: EMPTY,
      adx: EMPTY,
      adxSignal: `+DI ${EMPTY} / -DI ${EMPTY}`,
      cmf: EMPTY,
      techSummaryHtml: EMPTY,
    };
  }

  const ma20 = calcMA(data, settings.ma20Period);
  const ma50 = calcMA(data, settings.ma50Period);
  const ma200 = calcMA(data, settings.ma200Period);
  const ema12 = calcEMA(data, settings.emaPeriod);
  const bb = calcBB(data, settings.bbPeriod, settings.bbMultiplier);
  const keltner = calcKeltnerChannels(data, settings.kcPeriod, settings.kcMultiplier);
  const donchian = calcDonchianChannels(data, settings.donchianPeriod);
  const rsi = calcRSI(data, settings.rsiPeriod);
  const williamsr = calcWilliamsR(data, settings.williamsrPeriod);
  const mfi = calcMFI(data, settings.mfiPeriod);
  const roc = calcROC(data, settings.rocPeriod);
  const { macd, signal } = calcMACD(data, settings.macdFast, settings.macdSlow, settings.macdSignal);
  const { k, d } = calcStoch(data, settings.stochK, settings.stochD);
  const obv = calcOBV(data);
  const { plusDI, minusDI, adx } = calcADX(data, settings.adxPeriod);
  const cmf = calcCMF(data, settings.cmfPeriod);
  const ichimoku = calcIchimoku(
    data,
    settings.ichimokuConversion,
    settings.ichimokuBase,
    settings.ichimokuSpanB,
    settings.ichimokuDisplacement,
  );
  const superTrend = calcSuperTrend(data, settings.supertrendPeriod, settings.supertrendMultiplier);

  const latestBb = bb[bb.length - 1];
  const latestKeltner = keltner[keltner.length - 1];
  const latestDonchian = donchian[donchian.length - 1];
  const latestRsi = rsi[rsi.length - 1];
  const latestWilliamsR = williamsr[williamsr.length - 1];
  const latestMfi = mfi[mfi.length - 1];
  const latestRoc = roc[roc.length - 1];
  const latestMacd = macd[macd.length - 1];
  const latestSignal = signal[signal.length - 1];
  const latestK = k[k.length - 1];
  const latestD = d[d.length - 1];
  const latestObv = obv[obv.length - 1];
  const latestCmf = cmf[cmf.length - 1];
  const latestAdx = findLastDefinedValue(adx);
  const latestPlusDi = findLastDefinedValue(plusDI);
  const latestMinusDi = findLastDefinedValue(minusDI);
  const latestSpanA = findLastDefinedValue(ichimoku.spanA);
  const latestSpanB = findLastDefinedValue(ichimoku.spanB);
  const latestSuperTrend = findLastDefinedValue(superTrend.line);
  const latestSuperTrendDirection = findLastDefinedValue(superTrend.trend);

  const summaryParts = [];
  let bull = 0;
  let bear = 0;
  const price = data[data.length - 1].close;
  const latestMa20 = ma20[ma20.length - 1];
  const latestMa50 = ma50[ma50.length - 1];

  if (latestRsi > 70) {
    summaryParts.push(`<span class="dn">RSI(${settings.rsiPeriod}) 超買 (${latestRsi.toFixed(1)})</span>`);
    bear += 1;
  } else if (latestRsi < 30) {
    summaryParts.push(`<span class="up">RSI(${settings.rsiPeriod}) 超賣 (${latestRsi.toFixed(1)})</span>`);
    bull += 1;
  } else {
    summaryParts.push(`<span>RSI(${settings.rsiPeriod}) 中性 (${latestRsi?.toFixed(1) ?? EMPTY})</span>`);
  }

  if (latestMacd != null && latestSignal != null) {
    if (latestMacd > latestSignal) {
      summaryParts.push('<span class="up">MACD 多頭排列</span>');
      bull += 1;
    } else {
      summaryParts.push('<span class="dn">MACD 空頭排列</span>');
      bear += 1;
    }
  }

  if (latestMa20 && latestMa50) {
    if (price > latestMa20 && price > latestMa50) {
      summaryParts.push(`<span class="up">站上 MA${settings.ma20Period}/MA${settings.ma50Period}</span>`);
      bull += 2;
    } else if (price < latestMa20 && price < latestMa50) {
      summaryParts.push(`<span class="dn">跌破 MA${settings.ma20Period}/MA${settings.ma50Period}</span>`);
      bear += 2;
    }
  }

  if (latestSpanA != null && latestSpanB != null) {
    const cloudTop = Math.max(latestSpanA, latestSpanB);
    const cloudBottom = Math.min(latestSpanA, latestSpanB);
    if (price > cloudTop) {
      summaryParts.push('<span class="up">Ichimoku 雲層之上</span>');
      bull += 1;
    } else if (price < cloudBottom) {
      summaryParts.push('<span class="dn">Ichimoku 雲層之下</span>');
      bear += 1;
    } else {
      summaryParts.push('<span style="color:var(--amber)">Ichimoku 雲層內整理</span>');
    }
  }

  if (latestSuperTrend != null && latestSuperTrendDirection != null) {
    if (latestSuperTrendDirection > 0 && price >= latestSuperTrend) {
      summaryParts.push(`<span class="up">SuperTrend(${settings.supertrendPeriod},${settings.supertrendMultiplier}) 多頭支撐</span>`);
      bull += 1;
    } else if (latestSuperTrendDirection < 0 && price <= latestSuperTrend) {
      summaryParts.push(`<span class="dn">SuperTrend(${settings.supertrendPeriod},${settings.supertrendMultiplier}) 空頭壓制</span>`);
      bear += 1;
    }
  }

  if (latestAdx != null) {
    if (latestAdx >= 25) {
      summaryParts.push(`<span>${latestPlusDi > latestMinusDi ? "趨勢偏多" : "趨勢偏空"} / ADX ${latestAdx.toFixed(1)}</span>`);
    } else {
      summaryParts.push(`<span style="color:var(--text2)">ADX ${latestAdx.toFixed(1)}，趨勢強度普通</span>`);
    }
  }

  if (latestKeltner?.u != null && latestKeltner?.l != null) {
    if (price > latestKeltner.u) {
      summaryParts.push(`<span class="up">Keltner(${settings.kcPeriod},${settings.kcMultiplier}) 上軌突破</span>`);
      bull += 1;
    } else if (price < latestKeltner.l) {
      summaryParts.push(`<span class="dn">Keltner(${settings.kcPeriod},${settings.kcMultiplier}) 下軌跌破</span>`);
      bear += 1;
    }
  }

  if (latestDonchian?.u != null && latestDonchian?.l != null) {
    if (price >= latestDonchian.u) {
      summaryParts.push(`<span class="up">Donchian(${settings.donchianPeriod}) 創區間新高</span>`);
      bull += 1;
    } else if (price <= latestDonchian.l) {
      summaryParts.push(`<span class="dn">Donchian(${settings.donchianPeriod}) 跌破區間低點</span>`);
      bear += 1;
    }
  }

  if (latestMfi != null) {
    if (latestMfi >= 80) {
      summaryParts.push(`<span class="dn">MFI(${settings.mfiPeriod}) 過熱 (${latestMfi.toFixed(1)})</span>`);
      bear += 1;
    } else if (latestMfi <= 20) {
      summaryParts.push(`<span class="up">MFI(${settings.mfiPeriod}) 超賣 (${latestMfi.toFixed(1)})</span>`);
      bull += 1;
    }
  }

  if (latestCmf != null) {
    summaryParts.push(`<span>${latestCmf >= 0 ? "資金流入" : "資金流出"} / CMF ${latestCmf.toFixed(3)}</span>`);
    if (latestCmf >= 0) bull += 1;
    else bear += 1;
  }

  const total = bull + bear;
  const score = total ? Math.round((bull / total) * 100) : 50;
  const verdict =
    score >= 65
      ? `<span class="up">▲ 偏多 (${score}分)</span>`
      : score <= 35
        ? `<span class="dn">▼ 偏空 (${score}分)</span>`
        : `<span style="color:var(--amber)">◆ 中性 (${score}分)</span>`;

  return {
    ma20: ma20[ma20.length - 1]?.toFixed(2) ?? EMPTY,
    ma50: ma50[ma50.length - 1]?.toFixed(2) ?? EMPTY,
    ma200: ma200[ma200.length - 1]?.toFixed(2) ?? EMPTY,
    ema12: ema12[ema12.length - 1]?.toFixed(2) ?? EMPTY,
    bb: latestBb?.u ? `${latestBb.u.toFixed(2)} / ${latestBb.l.toFixed(2)}` : EMPTY,
    keltner: latestKeltner?.u ? `${latestKeltner.u.toFixed(2)} / ${latestKeltner.l.toFixed(2)}` : EMPTY,
    donchian: latestDonchian?.u ? `${latestDonchian.u.toFixed(2)} / ${latestDonchian.l.toFixed(2)}` : EMPTY,
    ichimoku:
      latestSpanA != null && latestSpanB != null
        ? `${price > Math.max(latestSpanA, latestSpanB) ? "雲上" : price < Math.min(latestSpanA, latestSpanB) ? "雲下" : "雲中"}`
        : EMPTY,
    supertrend:
      latestSuperTrend != null
        ? `${latestSuperTrendDirection > 0 ? "多頭" : "空頭"} @ ${latestSuperTrend.toFixed(2)}`
        : EMPTY,
    rsi: latestRsi?.toFixed(1) ?? EMPTY,
    rsiClass: latestRsi > 70 ? "dn" : latestRsi < 30 ? "up" : "",
    williamsr: latestWilliamsR?.toFixed(1) ?? EMPTY,
    mfi: latestMfi?.toFixed(1) ?? EMPTY,
    roc: latestRoc?.toFixed(2) ?? EMPTY,
    macd: latestMacd?.toFixed(3) ?? EMPTY,
    macdSignal: `Signal(${settings.macdSignal}): ${latestSignal?.toFixed(3) ?? EMPTY}`,
    stoch: latestK != null ? `K:${latestK.toFixed(1)} D:${(latestD ?? 0).toFixed(1)}` : EMPTY,
    atr: calcATR(data, settings.atrPeriod).toFixed(3),
    cci: (calcCCI(data, settings.cciPeriod) ?? EMPTY).toString(),
    obv: formatCompactNumber(latestObv),
    adx: latestAdx?.toFixed(1) ?? EMPTY,
    adxSignal: `+DI ${latestPlusDi?.toFixed(1) ?? EMPTY} / -DI ${latestMinusDi?.toFixed(1) ?? EMPTY}`,
    cmf: latestCmf?.toFixed(3) ?? EMPTY,
    techSummaryHtml: `${summaryParts.join("<br>")}<br><br>綜合評分：${verdict}`,
  };
}

export function runBacktestSimulation(data, options) {
  if (!data.length) {
    return { error: "目前沒有可回測的 K 線資料。" };
  }

  const filtered = data.filter((row) => row.date >= options.start && row.date <= options.end);
  if (filtered.length < 30) {
    return { error: "請確認日期範圍內有足夠資料。" };
  }

  const ma20 = calcMA(filtered, 20);
  const ma50 = calcMA(filtered, 50);
  const { macd, signal } = calcMACD(filtered);
  const rsi = calcRSI(filtered);

  let cash = options.capital;
  let position = 0;
  let entryPrice = 0;
  const trades = [];
  const equity = [options.capital];

  for (let index = 50; index < filtered.length; index += 1) {
    const price = filtered[index].close;
    let signalType = null;

    if (options.strategy.includes("MA")) {
      if (ma20[index] > ma50[index] && ma20[index - 1] <= ma50[index - 1]) signalType = "buy";
      if (ma20[index] < ma50[index] && ma20[index - 1] >= ma50[index - 1]) signalType = "sell";
    } else if (options.strategy.includes("RSI")) {
      if (rsi[index] < 30 && rsi[index - 1] >= 30) signalType = "buy";
      if (rsi[index] > 70 && rsi[index - 1] <= 70) signalType = "sell";
    } else if (options.strategy.includes("MACD")) {
      if (macd[index] > signal[index] && macd[index - 1] <= signal[index - 1]) signalType = "buy";
      if (macd[index] < signal[index] && macd[index - 1] >= signal[index - 1]) signalType = "sell";
    }

    if (position > 0) {
      const pct = (price - entryPrice) / entryPrice;
      if (pct <= -options.sl || pct >= options.tp) {
        signalType = "sell";
      }
    }

    if (signalType === "buy" && cash > 0) {
      const shares = Math.floor(cash / price / (1 + options.fee));
      const cost = shares * price * (1 + options.fee);
      if (shares > 0) {
        position = shares;
        cash -= cost;
        entryPrice = price;
        trades.push({ type: "buy", price, date: filtered[index].date });
      }
    } else if (signalType === "sell" && position > 0) {
      const proceeds = position * price * (1 - options.fee);
      const pnl = proceeds - position * entryPrice * (1 + options.fee);
      trades.push({ type: "sell", price, date: filtered[index].date, pnl });
      cash += proceeds;
      position = 0;
    }

    equity.push(cash + position * price);
  }

  if (position > 0) {
    const price = filtered[filtered.length - 1].close;
    cash += position * price * (1 - options.fee);
  }

  const finalEquity = cash;
  const totalReturn = (finalEquity / options.capital - 1) * 100;
  const wins = trades.filter((trade) => trade.type === "sell" && trade.pnl > 0).length;
  const sellTrades = trades.filter((trade) => trade.type === "sell").length;
  const winRate = sellTrades ? (wins / sellTrades) * 100 : 0;

  return {
    strategy: options.strategy,
    start: options.start,
    end: options.end,
    capital: options.capital,
    finalEquity,
    totalReturn,
    sellTrades,
    winRate,
    maxDrawdown: calcMaxDrawdown(equity),
    sharpe: calcSharpe(equity),
    bars: filtered.length,
  };
}

export function calcMaxDrawdown(equity) {
  let peak = equity[0];
  let maxDrawdown = 0;
  equity.forEach((value) => {
    if (value > peak) peak = value;
    const drawdown = ((peak - value) / peak) * 100;
    if (drawdown > maxDrawdown) maxDrawdown = drawdown;
  });
  return maxDrawdown;
}

export function calcSharpe(equity) {
  const returns = [];
  for (let index = 1; index < equity.length; index += 1) {
    returns.push((equity[index] - equity[index - 1]) / equity[index - 1]);
  }
  if (!returns.length) return 0;
  const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const std = Math.sqrt(returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / returns.length);
  return std ? mean / std * Math.sqrt(252) : 0;
}

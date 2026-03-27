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

export const calcMACD = (data) => {
  const ema12 = calcEMA(data, 12);
  const ema26 = calcEMA(data, 26);
  const macd = ema12.map((value, index) => Number((value - ema26[index]).toFixed(4)));
  const signal = calcEMA(macd.map((value) => ({ close: value || 0 })), 9);
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

export const calcATR = (data, n = 14) => {
  if (!data.length) {
    return 0;
  }
  let atr = 0;
  const start = Math.max(0, data.length - n);
  for (let index = start; index < data.length; index += 1) {
    const current = data[index];
    const previous = data[index - 1] || current;
    const trueRange = Math.max(
      current.high - current.low,
      Math.abs(current.high - previous.close),
      Math.abs(current.low - previous.close),
    );
    atr += trueRange / n;
  }
  return atr;
};

export const calcCCI = (data, n = 20) => {
  if (data.length < n) {
    return null;
  }
  const slice = data.slice(-n);
  const typicalPrices = slice.map((row) => (row.high + row.low + row.close) / 3);
  const mean = typicalPrices.reduce((sum, value) => sum + value, 0) / n;
  const meanDeviation = typicalPrices.reduce((sum, value) => sum + Math.abs(value - mean), 0) / n;
  return meanDeviation ? Number(((typicalPrices[typicalPrices.length - 1] - mean) / (0.015 * meanDeviation)).toFixed(2)) : null;
};

export function buildIndicatorSnapshot(data) {
  if (!data.length) {
    return {
      ma20: "—",
      ma50: "—",
      ma200: "—",
      ema12: "—",
      bb: "—",
      rsi: "—",
      rsiClass: "",
      macd: "—",
      macdSignal: "Signal: —",
      stoch: "—",
      atr: "—",
      cci: "—",
      techSummaryHtml: "—",
    };
  }

  const ma20 = calcMA(data, 20);
  const ma50 = calcMA(data, 50);
  const ma200 = calcMA(data, 200);
  const ema12 = calcEMA(data, 12);
  const bb = calcBB(data);
  const rsi = calcRSI(data);
  const { macd, signal } = calcMACD(data);
  const { k, d } = calcStoch(data);

  const latestBb = bb[bb.length - 1];
  const latestRsi = rsi[rsi.length - 1];
  const latestMacd = macd[macd.length - 1];
  const latestSignal = signal[signal.length - 1];
  const latestK = k[k.length - 1];
  const latestD = d[d.length - 1];

  const summaryParts = [];
  let bull = 0;
  let bear = 0;
  const price = data[data.length - 1].close;
  const latestMa20 = ma20[ma20.length - 1];
  const latestMa50 = ma50[ma50.length - 1];

  if (latestRsi > 70) {
    summaryParts.push(`<span class="dn">RSI 超買 (${latestRsi.toFixed(1)})</span>`);
    bear += 1;
  } else if (latestRsi < 30) {
    summaryParts.push(`<span class="up">RSI 超賣 (${latestRsi.toFixed(1)})</span>`);
    bull += 1;
  } else {
    summaryParts.push(`<span>RSI 中性 (${latestRsi?.toFixed(1) ?? "—"})</span>`);
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
      summaryParts.push('<span class="up">站上 MA20/MA50</span>');
      bull += 2;
    } else if (price < latestMa20 && price < latestMa50) {
      summaryParts.push('<span class="dn">跌破 MA20/MA50</span>');
      bear += 2;
    }
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
    ma20: ma20[ma20.length - 1]?.toFixed(2) ?? "—",
    ma50: ma50[ma50.length - 1]?.toFixed(2) ?? "—",
    ma200: ma200[ma200.length - 1]?.toFixed(2) ?? "—",
    ema12: ema12[ema12.length - 1]?.toFixed(2) ?? "—",
    bb: latestBb?.u ? `${latestBb.u.toFixed(2)} / ${latestBb.l.toFixed(2)}` : "—",
    rsi: latestRsi?.toFixed(1) ?? "—",
    rsiClass: latestRsi > 70 ? "dn" : latestRsi < 30 ? "up" : "",
    macd: latestMacd?.toFixed(3) ?? "—",
    macdSignal: `Signal: ${latestSignal?.toFixed(3) ?? "—"}`,
    stoch: latestK != null ? `K:${latestK.toFixed(1)} D:${(latestD ?? 0).toFixed(1)}` : "—",
    atr: calcATR(data).toFixed(3),
    cci: (calcCCI(data) ?? "—").toString(),
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
    if (value > peak) {
      peak = value;
    }
    const drawdown = ((peak - value) / peak) * 100;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
    }
  });
  return maxDrawdown;
}

export function calcSharpe(equity) {
  const returns = [];
  for (let index = 1; index < equity.length; index += 1) {
    returns.push((equity[index] - equity[index - 1]) / equity[index - 1]);
  }
  if (!returns.length) {
    return 0;
  }
  const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const std = Math.sqrt(returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / returns.length);
  return std ? mean / std * Math.sqrt(252) : 0;
}

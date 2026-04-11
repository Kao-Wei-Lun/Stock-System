export function fmtPrice(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }
  const numericValue = Number(value);
  if (numericValue >= 1000) {
    return numericValue.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return numericValue.toFixed(2);
}

export function fmtVol(value) {
  if (!value) {
    return "—";
  }
  if (value >= 1e9) {
    return `${(value / 1e9).toFixed(2)}B`;
  }
  if (value >= 1e6) {
    return `${(value / 1e6).toFixed(2)}M`;
  }
  if (value >= 1e3) {
    return `${(value / 1e3).toFixed(0)}K`;
  }
  return String(value);
}

export function fmtMktCap(value) {
  if (!value) {
    return "—";
  }
  if (value >= 1e12) {
    return `${(value / 1e12).toFixed(2)}T`;
  }
  if (value >= 1e9) {
    return `${(value / 1e9).toFixed(1)}B`;
  }
  if (value >= 1e6) {
    return `${(value / 1e6).toFixed(1)}M`;
  }
  return Number(value).toLocaleString();
}

export function fmtTwMoney(value, options = {}) {
  const { signed = false, empty = "—" } = options;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return empty;
  }
  if (numericValue === 0) {
    return "0";
  }

  const sign = signed ? (numericValue > 0 ? "+" : "-") : "";
  const absoluteValue = Math.abs(numericValue);

  if (absoluteValue >= 1e8) {
    const digits = absoluteValue >= 1e10 ? 0 : 1;
    return `${sign}${(absoluteValue / 1e8).toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits,
    })}億`;
  }

  if (absoluteValue >= 1e4) {
    return `${sign}${(absoluteValue / 1e4).toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 1,
    })}萬`;
  }

  return `${sign}${absoluteValue.toLocaleString()}`;
}

const EMPTY_MARK = "\u2014";
const TW_HUNDRED_MILLION = "\u5104";
const TW_TEN_THOUSAND = "\u842c";

export function fmtPrice(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return EMPTY_MARK;
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
  if (value == null || value === "") {
    return EMPTY_MARK;
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return EMPTY_MARK;
  }
  if (numericValue === 0) {
    return "0";
  }
  if (numericValue >= 1e9) {
    return `${(numericValue / 1e9).toFixed(2)}B`;
  }
  if (numericValue >= 1e6) {
    return `${(numericValue / 1e6).toFixed(2)}M`;
  }
  if (numericValue >= 1e3) {
    return `${(numericValue / 1e3).toFixed(0)}K`;
  }
  return String(numericValue);
}

export function fmtMktCap(value) {
  if (!value) {
    return EMPTY_MARK;
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
  const { signed = false, empty = EMPTY_MARK } = options;
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
    })}${TW_HUNDRED_MILLION}`;
  }

  if (absoluteValue >= 1e4) {
    return `${sign}${(absoluteValue / 1e4).toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 1,
    })}${TW_TEN_THOUSAND}`;
  }

  return `${sign}${absoluteValue.toLocaleString()}`;
}

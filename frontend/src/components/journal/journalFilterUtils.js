export function buildJournalTagPreset(tag) {
  return {
    tag,
    search: "",
  };
}

export function buildJournalStrategyPreset(strategyCode) {
  return {
    strategy_code: strategyCode,
    search: "",
  };
}

export function getJournalEntryPlainTags(entry) {
  return (entry?.tags || [])
    .map((tag) => String(tag || "").trim())
    .filter((tag) => tag && !tag.startsWith("來源:") && !tag.startsWith("市場:"));
}

function findJournalEntryPrefixedTag(entry, prefix) {
  return (entry?.tags || [])
    .map((tag) => String(tag || "").trim())
    .find((tag) => tag.startsWith(prefix)) || "";
}

export function buildJournalQuickSaveDraft(context, name, partialPreset, description) {
  const filters = {
    market: context?.journalFilters?.market || "",
    strategy_code: context?.journalFilters?.strategy_code || "",
    tag: context?.journalFilters?.tag || "",
    search: context?.journalFilters?.search || "",
  };
  const source = partialPreset && typeof partialPreset === "object" ? partialPreset : {};
  const mergedFilters = source.filters && typeof source.filters === "object"
    ? { ...filters, ...source.filters }
    : { ...filters, ...source };
  return {
    name,
    description,
    scope: Object.prototype.hasOwnProperty.call(source, "scope")
      ? (source.scope === "all" ? "all" : "ticker")
      : (context?.journalFilterScope === "all" ? "all" : "ticker"),
    filters: {
      market: mergedFilters.market || "",
      strategy_code: mergedFilters.strategy_code || "",
      tag: mergedFilters.tag || "",
      search: mergedFilters.search || "",
    },
  };
}

export function getJournalEntryQuickFilters(entry, context) {
  const quickFilters = [];
  const strategyCode = String(entry?.strategy_code || "").trim();
  const sourceTag = findJournalEntryPrefixedTag(entry, "來源:");
  const marketPostureTag = findJournalEntryPrefixedTag(entry, "市場:");

  if (sourceTag) {
    const label = `來源：${sourceTag.slice(3)}`;
    quickFilters.push({
      kind: "source",
      value: sourceTag.slice(3),
      label,
      preset: buildJournalTagPreset(sourceTag),
      saveDraft: buildJournalQuickSaveDraft(context, label, buildJournalTagPreset(sourceTag), "由歷史紀錄快速建立"),
    });
  }

  if (marketPostureTag) {
    const label = `市場：${marketPostureTag.slice(3)}`;
    quickFilters.push({
      kind: "posture",
      value: marketPostureTag.slice(3),
      label,
      preset: buildJournalTagPreset(marketPostureTag),
      saveDraft: buildJournalQuickSaveDraft(context, label, buildJournalTagPreset(marketPostureTag), "由歷史紀錄快速建立"),
    });
  }

  if (strategyCode) {
    const label = `策略：${strategyCode}`;
    quickFilters.push({
      kind: "strategy",
      value: strategyCode,
      label,
      preset: buildJournalStrategyPreset(strategyCode),
      saveDraft: buildJournalQuickSaveDraft(context, label, buildJournalStrategyPreset(strategyCode), "由歷史紀錄快速建立"),
    });
  }

  return quickFilters;
}

export function normalizeJournalFilterSnapshot(source) {
  const filters = source?.filters && typeof source.filters === "object"
    ? source.filters
    : source || {};
  return {
    scope: source?.scope === "all" ? "all" : "ticker",
    filters: {
      market: String(filters.market || "").trim(),
      strategy_code: String(filters.strategy_code || "").trim(),
      tag: String(filters.tag || "").trim(),
      search: String(filters.search || "").trim(),
    },
  };
}

export function isSameJournalFilterSnapshot(left, right) {
  if (!left || !right) return false;
  if (left.scope !== right.scope) return false;
  return ["market", "strategy_code", "tag", "search"].every(
    (key) => String(left.filters?.[key] || "") === String(right.filters?.[key] || ""),
  );
}

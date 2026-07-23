import { computed, isRef, shallowRef } from "vue";

const ARRAY_KEYS = new Set([
  "assetAccounts",
  "assetCashEntries",
  "assetTradeEntries",
  "assetReconciliationEntries",
  "assetPriceOverrides",
  "assetFxRates",
  "assetAdjustments",
  "assetImportBatches",
  "assetAlerts",
  "assetHoldings",
  "assetWarnings",
  "assetQuoteGaps",
  "assetAccountAllocation",
  "assetMarketAllocation",
  "assetCurrencyAllocation",
  "assetContributors",
  "assetPerformanceSeries",
  "assetMonthlyHeatmap",
]);

const NULL_KEYS = new Set([
  "assetPortfolio",
  "assetPerformance",
  "assetTradeImportResult",
  "assetCashImportResult",
  "assetJournalImportPreview",
  "assetLastRecompute",
]);

const OBJECT_KEYS = new Set([
  "assetSummary",
  "assetAccountsSummary",
  "assetReconciliation",
  "assetPortfolioCalculationMetadata",
  "assetPortfolioDataQualitySummary",
  "assetPerformanceSummary",
  "assetPerformanceCalculationMetadata",
  "assetPerformanceDataQualitySummary",
  "assetRealizedVsUnrealized",
]);

const STATE_KEYS = [
  "assetLoading",
  "assetError",
  "assetPerformanceRange",
  "assetAccounts",
  "assetCashEntries",
  "assetTradeEntries",
  "assetReconciliationEntries",
  "assetPriceOverrides",
  "assetFxRates",
  "assetAdjustments",
  "assetImportBatches",
  "assetPortfolio",
  "assetPerformance",
  "assetAlerts",
  "assetTradeImportResult",
  "assetCashImportResult",
  "assetJournalImportPreview",
  "assetLastRecompute",
  "assetBaseCurrency",
  "assetSummary",
  "assetAccountsSummary",
  "assetHoldings",
  "assetWarnings",
  "assetQuoteGaps",
  "assetReconciliation",
  "assetPortfolioCalculationMetadata",
  "assetPortfolioDataQualitySummary",
  "assetAccountAllocation",
  "assetMarketAllocation",
  "assetCurrencyAllocation",
  "assetContributors",
  "assetPerformanceSummary",
  "assetPerformanceCalculationMetadata",
  "assetPerformanceDataQualitySummary",
  "assetPerformanceSeries",
  "assetMonthlyHeatmap",
  "assetRealizedVsUnrealized",
  "assetAccountForm",
  "assetCashForm",
  "assetTradeForm",
  "assetReconciliationForm",
  "assetPriceOverrideForm",
  "assetFxRateForm",
  "assetAdjustmentForm",
  "assetTradeImportForm",
  "assetCashImportForm",
  "assetJournalImportForm",
];

const ACTION_KEYS = [
  "loadAssetTrackingData",
  "loadAssetPerformance",
  "setAssetPerformanceRange",
  "updateAssetAccountField",
  "updateAssetCashField",
  "updateAssetTradeField",
  "updateAssetReconciliationField",
  "updateAssetPriceOverrideField",
  "updateAssetFxRateField",
  "updateAssetAdjustmentField",
  "updateAssetTradeImportField",
  "updateAssetCashImportField",
  "updateAssetJournalImportField",
  "editAssetAccount",
  "editAssetCashEntry",
  "editAssetTradeEntry",
  "editAssetPriceOverride",
  "editAssetFxRate",
  "editAssetAdjustment",
  "resetAssetAccountForm",
  "resetAssetCashForm",
  "resetAssetTradeForm",
  "resetAssetReconciliationForm",
  "resetAssetPriceOverrideForm",
  "resetAssetFxRateForm",
  "resetAssetAdjustmentForm",
  "resetAssetImportForms",
  "resetAssetJournalImportForm",
  "saveAssetAccount",
  "saveAssetCashEntry",
  "saveAssetTradeEntry",
  "saveAssetReconciliation",
  "saveAssetPriceOverride",
  "saveAssetFxRate",
  "saveAssetAdjustment",
  "deleteAssetAccount",
  "deleteAssetCashEntry",
  "deleteAssetTradeEntry",
  "deleteAssetReconciliation",
  "deleteAssetPriceOverride",
  "deleteAssetFxRate",
  "deleteAssetAdjustment",
  "importAssetTradesCsv",
  "importAssetCashCsv",
  "rollbackAssetImportBatch",
  "previewAssetJournalImport",
  "importAssetJournalEntries",
  "recomputeAssetTracking",
];

const EMPTY_FORMS = Object.freeze({
  assetAccountForm: Object.freeze({}),
  assetCashForm: Object.freeze({}),
  assetTradeForm: Object.freeze({}),
  assetReconciliationForm: Object.freeze({}),
  assetPriceOverrideForm: Object.freeze({}),
  assetFxRateForm: Object.freeze({}),
  assetAdjustmentForm: Object.freeze({}),
  assetTradeImportForm: Object.freeze({}),
  assetCashImportForm: Object.freeze({}),
  assetJournalImportForm: Object.freeze({}),
});

function defaultValue(key) {
  if (ARRAY_KEYS.has(key)) return [];
  if (NULL_KEYS.has(key)) return null;
  if (OBJECT_KEYS.has(key)) return {};
  if (key === "assetLoading") return false;
  if (key === "assetPerformanceRange") return "1y";
  if (key === "assetBaseCurrency") return "TWD";
  if (Object.hasOwn(EMPTY_FORMS, key)) return EMPTY_FORMS[key];
  return "";
}

function unwrapControllerValue(value) {
  return isRef(value) ? value.value : value;
}

/**
 * Keeps the public dashboard contract stable while moving the sizeable asset
 * controller out of the terminal's initial dependency graph.
 */
export function createLazyDashboardAssetTracking(
  options,
  loadModule = () => import("./dashboardAssetTracking"),
) {
  const controller = shallowRef(null);
  let loadPromise = null;

  const ensureController = async () => {
    if (controller.value) return controller.value;
    if (!loadPromise) {
      loadPromise = loadModule()
        .then(({ createDashboardAssetTracking }) => {
          controller.value = createDashboardAssetTracking(options);
          return controller.value;
        })
        .catch((error) => {
          loadPromise = null;
          throw error;
        });
    }
    return loadPromise;
  };

  const facade = {
    ensureAssetController: ensureController,
  };

  for (const key of STATE_KEYS) {
    const fallback = defaultValue(key);
    facade[key] = computed(() => {
      const value = unwrapControllerValue(controller.value?.[key]);
      return value === undefined ? fallback : value;
    });
  }

  for (const key of ACTION_KEYS) {
    facade[key] = async (...args) => {
      const loadedController = await ensureController();
      return loadedController[key](...args);
    };
  }

  return facade;
}

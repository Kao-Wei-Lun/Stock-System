import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ChartWorkspaceMetaBar from "./ChartWorkspaceMetaBar.vue";


function props(overrides = {}) {
  return {
    visibleRangeLabel: "A → B",
    visibleBarsLabel: "120 根",
    visibleChangeLabel: "+1%",
    zoomLabel: "100%",
    yScaleLabel: "Y 軸 手動鎖定 90 - 110",
    yScaleClipped: true,
    priceScaleModeLabel: "線性",
    quoteTimestampLabel: "now",
    quoteSourceLabel: "local",
    quoteDelayLabel: "快照",
    quoteFreshnessLabel: "有效",
    interactionHint: "hint",
    quote: { is_delayed: true },
    ...overrides,
  };
}


describe("ChartWorkspaceMetaBar", () => {
  it("announces clipped candles and supports keyboard-accessible auto recovery", async () => {
    const wrapper = mount(ChartWorkspaceMetaBar, { props: props() });
    const button = wrapper.get("button.y-scale-chip");

    expect(button.text()).toContain("資料超出範圍");
    expect(button.attributes("aria-label")).toContain("恢復自動縮放");
    await button.trigger("click");
    expect(wrapper.emitted("reset-y-scale")).toHaveLength(1);
  });

  it("disables the recovery chip while already in auto mode", () => {
    const wrapper = mount(ChartWorkspaceMetaBar, {
      props: props({ yScaleLabel: "Y 軸 自動 90 - 110", yScaleClipped: false }),
    });

    expect(wrapper.get("button.y-scale-chip").attributes("disabled")).toBeDefined();
  });
});

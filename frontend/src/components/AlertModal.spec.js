import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AlertModal from "./AlertModal.vue";

describe("AlertModal", () => {
  it("shows MACD cross conditions and disables numeric input when crossing", () => {
    const wrapper = mount(AlertModal, {
      props: {
        isOpen: true,
        form: {
          ticker: "AAPL",
          type: "macd",
          cond: "上穿",
          value: "",
        },
      },
    });

    const selects = wrapper.findAll("select");
    const conditionOptions = selects[1].findAll("option").map((item) => item.text());
    const valueInput = wrapper.find('input[type="number"]');

    expect(conditionOptions).toContain("黃金交叉");
    expect(conditionOptions).toContain("死亡交叉");
    expect(valueInput.attributes("disabled")).toBeDefined();
  });

  it("shows volume helper text and keeps numeric input enabled", () => {
    const wrapper = mount(AlertModal, {
      props: {
        isOpen: true,
        form: {
          ticker: "AAPL",
          type: "volume",
          cond: "大於",
          value: "2",
        },
      },
    });

    const valueInput = wrapper.find('input[type="number"]');

    expect(wrapper.text()).toContain("量比異常會以近 20 根日 K 的平均量作為基準");
    expect(valueInput.attributes("disabled")).toBeUndefined();
  });

  it("supports market risk alerts without ticker or numeric input", () => {
    const wrapper = mount(AlertModal, {
      props: {
        isOpen: true,
        form: {
          ticker: "MARKET",
          type: "market_risk",
          cond: "high",
          value: "",
        },
      },
    });

    const selects = wrapper.findAll("select");
    const conditionOptions = selects[1].findAll("option").map((item) => item.text());
    const inputs = wrapper.findAll("input");
    const tickerInput = inputs[0];
    const valueInput = wrapper.find('input[type="number"]');

    expect(conditionOptions).toContain("進入高風險");
    expect(conditionOptions).toContain("進入 risk-off");
    expect(tickerInput.attributes("disabled")).toBeDefined();
    expect(valueInput.attributes("disabled")).toBeDefined();
    expect(valueInput.attributes("placeholder")).toBe("市場型警報不需填數值");
    expect(wrapper.text()).toContain("市場風險警報會直接讀取本地 macro_snapshots");
  });
});

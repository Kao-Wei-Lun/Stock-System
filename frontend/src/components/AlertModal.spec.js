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

  it("supports basis alerts with percentage thresholds", () => {
    const wrapper = mount(AlertModal, {
      props: {
        isOpen: true,
        form: {
          ticker: "^TWII",
          type: "basis",
          cond: "大於",
          value: "1.5",
        },
      },
    });

    expect(wrapper.text()).toContain("Basis 偏離預設以期現貨差值百分比判斷");
    expect(wrapper.find('input[type="number"]').attributes("placeholder")).toBe("1.5 或 -1.5");
  });

  it("supports institutional anomaly alerts without numeric input", () => {
    const wrapper = mount(AlertModal, {
      props: {
        isOpen: true,
        form: {
          ticker: "^TWII",
          type: "institutional",
          cond: "high",
          value: "",
        },
      },
    });

    const conditionOptions = wrapper.findAll("select")[1].findAll("option").map((item) => item.text());
    expect(conditionOptions).toContain("高異常");
    expect(conditionOptions).toContain("中度以上異常");
    expect(wrapper.find('input[type="number"]').attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("法人異常警報會根據近窗期貨、選擇權與現貨資料");
  });

  it("supports event reminders with lead-day thresholds", () => {
    const wrapper = mount(AlertModal, {
      props: {
        isOpen: true,
        form: {
          ticker: "AAPL",
          type: "event",
          cond: "within_days",
          value: "3",
        },
      },
    });

    const conditionOptions = wrapper.findAll("select")[1].findAll("option").map((item) => item.text());
    expect(conditionOptions).toContain("事件前提醒");
    expect(wrapper.find('input[type="number"]').attributes("placeholder")).toBe("例如 3 或 7");
    expect(wrapper.text()).toContain("事件提醒會在未來 N 日內出現符合條件的事件時觸發");
  });

  it("shows watchlist prefill hint and context tags", () => {
    const wrapper = mount(AlertModal, {
      props: {
        isOpen: true,
        form: {
          ticker: "AAPL",
          type: "price",
          cond: "大於",
          value: "210.5",
          prefill_hint: "觀察池快捷警報：以 210.5 為基準，資料源 Yahoo Finance。",
          context_tags: ["優先候選", "Q4", "市場:選擇性出手"],
        },
      },
    });

    expect(wrapper.text()).toContain("觀察池快捷警報：以 210.5 為基準");
    expect(wrapper.text()).toContain("優先候選");
    expect(wrapper.text()).toContain("Q4");
    expect(wrapper.find('input[type="number"]').element.value).toBe("210.5");
  });
});

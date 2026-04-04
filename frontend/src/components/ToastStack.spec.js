import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ToastStack from "./ToastStack.vue";

describe("ToastStack", () => {
  it("renders unread session notifications and emits dismiss", async () => {
    const wrapper = mount(ToastStack, {
      props: {
        notifications: [
          { id: "session-1", category: "session", read: false, title: "同步完成", msg: "AAPL 已更新", icon: "✓" },
          { id: "remote-1", category: "system", read: false, title: "遠端通知", msg: "忽略", icon: "!" },
          { id: "session-2", category: "session", read: true, title: "已讀提示", msg: "不顯示", icon: "•" },
        ],
      },
    });

    expect(wrapper.text()).toContain("同步完成");
    expect(wrapper.text()).not.toContain("遠端通知");
    expect(wrapper.text()).not.toContain("已讀提示");

    await wrapper.get(".toast-dismiss").trigger("click");

    expect(wrapper.emitted("dismiss")).toEqual([["session-1"]]);
  });
});

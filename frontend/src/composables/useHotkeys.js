import { onBeforeUnmount, onMounted } from "vue";

function isEditableTarget(target) {
  return target instanceof HTMLInputElement
    || target instanceof HTMLTextAreaElement
    || target instanceof HTMLSelectElement
    || target?.isContentEditable;
}

function matchesBinding(event, binding) {
  const eventKey = String(event.key || "").toLowerCase();
  const bindingKey = String(binding.key || "").toLowerCase();
  if (eventKey !== bindingKey) return false;

  if (binding.ctrlOrMeta) {
    if (!(event.ctrlKey || event.metaKey)) return false;
  } else if (Boolean(event.ctrlKey) !== Boolean(binding.ctrlKey)) {
    return false;
  }

  if (!binding.ctrlOrMeta && Boolean(event.metaKey) !== Boolean(binding.metaKey)) {
    return false;
  }

  if (Boolean(event.altKey) !== Boolean(binding.altKey)) return false;
  if (Boolean(event.shiftKey) !== Boolean(binding.shiftKey)) return false;

  return true;
}

export function useHotkeys(bindings) {
  const resolveBindings = () => (typeof bindings === "function" ? bindings() : bindings) || [];

  function handleKeydown(event) {
    for (const binding of resolveBindings()) {
      if (!binding || binding.disabled) continue;
      if (!binding.allowInInputs && isEditableTarget(event.target)) continue;
      if (!matchesBinding(event, binding)) continue;
      if (binding.preventDefault) event.preventDefault();
      if (binding.stopPropagation) event.stopPropagation();
      binding.handler?.(event);
      return;
    }
  }

  onMounted(() => {
    window.addEventListener("keydown", handleKeydown);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("keydown", handleKeydown);
  });
}

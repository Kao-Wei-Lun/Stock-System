<template>
  <div class="notif-panel">
    <div v-for="item in notifications" :key="item.id" class="notif" :class="item.type">
      <div class="notif-icon">{{ item.icon }}</div>
      <div class="notif-body">
        <div class="notif-title">{{ item.title }}</div>
        <div class="notif-msg">{{ item.msg }}</div>
        <div class="notif-time">{{ item.time }}</div>
      </div>
      <div class="notif-close" @click="$emit('dismiss', item.id)">✕</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  notifications: { type: Array, required: true },
});

defineEmits(["dismiss"]);
</script>

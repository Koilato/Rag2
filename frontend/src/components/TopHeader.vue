<template>
  <div class="top-header-tabs">
    <div class="tabs">
      <div class="tab-item active">会话</div>
      <div class="tab-item">数据库</div>
    </div>
  </div>
</template>

<script setup>
// No script needed for this simple component
</script>

<style scoped>
.top-header-tabs {
  display: flex;
  align-items: flex-end;
  height: 48px;
  padding: 0 16px;
  border-bottom: 1px solid #e8eaed;
  background-color: #F7F7FA; /* Match the column background */
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.tabs {
  display: flex;
  height: 100%;
}

.tab-item {
  display: flex;
  align-items: center;
  padding: 0 16px;
  cursor: pointer;
  color: #5f6368;
  font-size: 14px;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px; /* Align with the main border */
}

.tab-item.active {
  color: #3f51b5;
  border-bottom-color: #3f51b5;
  font-weight: 500;
}

.tab-item:hover {
  background-color: #f1f3f4;
}
</style>

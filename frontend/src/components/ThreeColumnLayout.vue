<template>
  <div class="three-column-layout" :style="layoutStyles">
    <LeftColumn :username="username" />
    <div class="splitter" @mousedown="startDrag($event, 'left')"></div>
    <MiddleColumn 
      :isMiddleCollapsed="isMiddleCollapsed"
      v-model:cve="cve"
      v-model:uuid="uuid"
      v-model:host="host"
      v-model:startTime="startDate"
      v-model:endTime="endDate"
      v-model:autoExportEnabled="autoExportReport"
      v-model:onlineSearchEnabled="webSearch"
      v-model:plugin_id="pluginId"
      v-model:risk="risk"
      v-model:protocol="protocol"
    />
    <div class="splitter" @mousedown="startDrag($event, 'right')">
        <div class="collapse-handle" @click.stop="toggleMiddleColumn">
            <span class="arrow" :class="{ 'arrow-right': !isMiddleCollapsed, 'arrow-left': isMiddleCollapsed }"></span>
        </div>
    </div>
    <RightColumn 
      @export-report="handleExportReport"
      :cve="cve"
      :uuid="uuid"
      :host="host"
      :startDate="startDate"
      :endDate="endDate"
      :autoExportReport="autoExportReport"
      :webSearch="webSearch"
      :pluginId="pluginId"
      :risk="risk"
      :protocol="protocol"
      :username="username"
    />
  </div>
</template>

<script setup>
import { defineProps, ref, onUnmounted, computed } from 'vue';
import LeftColumn from './LeftColumn.vue';
import MiddleColumn from './MiddleColumn.vue';
import RightColumn from './RightColumn.vue';
import { exportReport } from '../utils.js';

// Define props
const props = defineProps({
  username: {
    type: String,
    required: true
  }
});

// --- State Hoisting ---
// All shared state is now managed in the parent component.
const cve = ref('');
const uuid = ref('');
const host = ref('');
const startDate = ref('');
const endDate = ref('');
const autoExportReport = ref(true);
const webSearch = ref(true);

const pluginId = ref('');
const risk = ref('');
const protocol = ref('');

// This function is no longer needed as RightColumn gets props directly
const handleSubmission = () => {
  // The submission logic is now self-contained within RightColumn,
  // which has all the necessary data via props.
  console.log('Submission triggered.');
};

const handleExportReport = () => {
  const params = {
    cve: cve.value,
    uuid: uuid.value,
    host: host.value,
    plugin_id: pluginId.value,
    risk: risk.value,
    protocol: protocol.value,
    start_date: startDate.value,
    end_date: endDate.value,
    auto_export_report: autoExportReport.value,
    web_search: webSearch.value,
  };
  exportReport(params);
};

const leftColumnWidth = ref(300);
const middleColumnWidth = ref(400);
const isMiddleCollapsed = ref(false);
const middleColumnWidthBeforeCollapse = ref(400);

const dragging = ref(false);
const initialMouseX = ref(0);
const initialLeftWidth = ref(0);
const initialMiddleWidth = ref(0);
const dragTarget = ref(null);
let animationFrameId = null;

const layoutStyles = computed(() => ({
  '--left-column-width': `${leftColumnWidth.value}px`,
  '--middle-column-width': `${middleColumnWidth.value}px`
}));

const toggleMiddleColumn = () => {
  isMiddleCollapsed.value = !isMiddleCollapsed.value;
  if (isMiddleCollapsed.value) {
    middleColumnWidthBeforeCollapse.value = middleColumnWidth.value;
    middleColumnWidth.value = 0;
  } else {
    middleColumnWidth.value = middleColumnWidthBeforeCollapse.value;
  }
};

const startDrag = (e, target) => {
  dragging.value = true;
  initialMouseX.value = e.clientX;
  initialLeftWidth.value = document.querySelector('.left-column').offsetWidth;
  initialMiddleWidth.value = document.querySelector('.middle-column').offsetWidth;
  dragTarget.value = target;

  document.addEventListener('mousemove', doDrag);
  document.addEventListener('mouseup', stopDrag);
  document.body.style.cursor = 'ew-resize';
  document.body.style.userSelect = 'none';
};

const doDrag = (e) => {
  if (!dragging.value) return;

  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
  }

  animationFrameId = requestAnimationFrame(() => {
    const dx = e.clientX - initialMouseX.value;

    if (dragTarget.value === 'left') {
      const newLeftWidth = initialLeftWidth.value + dx;
      if (newLeftWidth > 100 && newLeftWidth < window.innerWidth - middleColumnWidth.value - 100) {
        leftColumnWidth.value = newLeftWidth;
      }
    } else if (dragTarget.value === 'right') {
      const newMiddleWidth = initialMiddleWidth.value + dx;
      if (newMiddleWidth > 100 && newMiddleWidth < window.innerWidth - leftColumnWidth.value - 100) {
        middleColumnWidth.value = newMiddleWidth;
      }
    }
  });
};

const stopDrag = () => {
  dragging.value = false;
  document.removeEventListener('mousemove', doDrag);
  document.removeEventListener('mouseup', stopDrag);
  document.body.style.cursor = 'default';
  document.body.style.userSelect = 'auto';
};

onUnmounted(() => {
  document.removeEventListener('mousemove', doDrag);
  // **这里是缺失的部分：**
  document.removeEventListener('mouseup', stopDrag); // 移除 mouseup 监听器
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId); // 清除可能存在的动画帧
  }
}); // **onUnmounted 函数的结束大括号**
</script>

<style scoped> /* 添加 scoped 是个好习惯 */
.three-column-layout {
  display: flex;
  height: 100vh; /* Full viewport height */
  overflow: hidden; /* Prevent body scrollbars */
}

/* 假设 LeftColumn, MiddleColumn, RightColumn 有自己的样式或通过slot控制宽度 */
/* 例如，可以在这里设置flex-grow/shrink/basis */
/* 
.left-column, .middle-column, .right-column {
  flex-grow: 0;
  flex-shrink: 0;
}
.left-column {
  flex-basis: var(--left-column-width);
}
.middle-column {
  flex-basis: var(--middle-column-width);
}
.right-column {
  flex-grow: 1; 
  flex-basis: 0; // 让右侧填充剩余空间
}
*/

/* 为LeftColumn, MiddleColumn, RightColumn添加基本样式，以便它们能被选择器正确选中 */
/* 你需要在 LeftColumn.vue, MiddleColumn.vue, RightColumn.vue 文件中为它们的根元素添加类名 */
.left-column { /* 确保 LeftColumn.vue 的根元素有 class="left-column" */
    width: var(--left-column-width);
    flex-shrink: 0;
    overflow-y: auto; /* Allow content to scroll if needed */
    background-color: #f0f0f0; /* 示例颜色 */
}

.middle-column { /* 确保 MiddleColumn.vue 的根元素有 class="middle-column" */
    width: var(--middle-column-width);
    flex-shrink: 0;
    overflow-y: auto;
    background-color: #f8f8f8; /* 示例颜色 */
    transition: width 0.2s ease-out; /* 平滑过渡折叠效果 */
}

.right-column { /* 确保 RightColumn.vue 的根元素有 class="right-column" */
    flex-grow: 1; /* Make it fill remaining space */
    overflow-y: auto;
    background-color: #ffffff; /* 示例颜色 */
}


.splitter {
  width: 1px;
  background-color: #e8eaed;
  cursor: ew-resize;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}

.splitter::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: -6px;
  right: -6px;
  background: transparent;
}

.collapse-handle {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 24px;
  height: 40px;
  background-color: #fff;
  border: 1px solid #e8eaed;
  border-radius: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s ease;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.splitter:hover .collapse-handle {
  opacity: 1;
}

.collapse-handle .arrow {
  width: 0;
  height: 0;
  border-style: solid;
}

.collapse-handle .arrow-left {
  border-width: 6px 0 6px 6px;
  border-color: transparent transparent transparent #5f6368;
  margin-left: -3px;
}

.collapse-handle .arrow-right {
  border-width: 6px 6px 6px 0;
  border-color: transparent #5f6368 transparent transparent;
  margin-right: -3px;
}
</style>

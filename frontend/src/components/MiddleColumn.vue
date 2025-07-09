<template>
  <div class="middle-column" :class="{ collapsed: isMiddleCollapsed }">
    <!-- 中间内容 -->
    <div class="header">
      <h2>参数设置</h2>
    </div>
    <div class="content">
      <div class="section">
        <h3>参数</h3>
        <div class="item">
          <span class="arrow">></span> CVE
        </div>
        <textarea :value="cve" @input="$emit('update:cve', $event.target.value)" class="uniform-textarea" placeholder="用逗号分隔..."></textarea>
        <div class="item">
          <span class="arrow">></span> UUID
        </div>
        <textarea :value="uuid" @input="$emit('update:uuid', $event.target.value)" class="uniform-textarea" placeholder="用逗号分隔..."></textarea>
        <div class="item">
          <span class="arrow">></span> Host
        </div>
        <textarea :value="host" @input="$emit('update:host', $event.target.value)" class="uniform-textarea" placeholder="用逗号分隔..."></textarea>
        <div class="item">
          <span class="arrow">></span> Plugin Id
        </div>
        <textarea :value="plugin_id" @input="$emit('update:plugin_id', $event.target.value)" class="uniform-textarea" placeholder="用逗号分隔..."></textarea>
        <div class="item">
          <span class="arrow">></span> Risk
        </div>
        <textarea :value="risk" @input="$emit('update:risk', $event.target.value)" class="uniform-textarea" placeholder="用逗号分隔..."></textarea>
        <div class="item">
          <span class="arrow">></span> Protocol
        </div>
        <textarea :value="protocol" @input="$emit('update:protocol', $event.target.value)" class="uniform-textarea" placeholder="用逗号分隔..."></textarea>
        <div class="item">
          <span class="arrow">></span> 时间范围
        </div>
        <div class="time-range-picker">
          <textarea :value="startTime" @input="$emit('update:startTime', $event.target.value)" class="uniform-textarea" placeholder="开始时间：YYYY-MM-DD"></textarea>
          <span>~</span>
          <textarea :value="endTime" @input="$emit('update:endTime', $event.target.value)" class="uniform-textarea" placeholder="结束时间：YYYY-MM-DD"></textarea>
        </div>
      </div>
      <div class="section">
        <h3>工具</h3>
        <div class="item">
          <span class="arrow">></span> 自动导出报告
          <button 
            class="toggle-switch" 
            :class="{ 'is-active': autoExportEnabled }"
            @click="$emit('update:autoExportEnabled', !autoExportEnabled)">
            <span class="toggle-knob"></span>
          </button>
        </div>
        <div class="item">
          <span class="arrow">></span> 联网搜索
          <button 
            class="toggle-switch" 
            :class="{ 'is-active': onlineSearchEnabled }"
            @click="$emit('update:onlineSearchEnabled', !onlineSearchEnabled)">
            <span class="toggle-knob"></span>
          </button>
        </div>
      </div>
      <div class="section">
        <h3>文件导入</h3>
        <div class="item" @click="triggerFileUpload">
          <span class="arrow">></span> 导入CSV文件
          <input type="file" ref="fileInput" @change="handleFileSelected" style="display: none" accept=".csv" />
          <span class="add-button">+</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useFileUpload } from '../utils.js';

const props = defineProps({
  isMiddleCollapsed: Boolean,
  cve: String,
  uuid: String,
  host: String,
  startTime: String,
  endTime: String,
  autoExportEnabled: Boolean,
  onlineSearchEnabled: Boolean,
  // Props for currently unused fields, can be added later
  plugin_id: String,
  risk: String,
  protocol: String,
});

const emit = defineEmits([
  'update:cve',
  'update:uuid',
  'update:host',
  'update:startTime',
  'update:endTime',
  'update:autoExportEnabled',
  'update:onlineSearchEnabled',
  'update:plugin_id',
  'update:risk',
  'update:protocol',
]);

// Use the file upload composable
const { fileInput, triggerFileUpload, handleFileSelected } = useFileUpload();

// No longer need defineExpose as state is managed by the parent
</script>

<style scoped>
.middle-column {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: 16px;
  background-color: #F7F7FA;
  border-right: 1px solid #e8eaed;
  overflow: hidden;
  flex-basis: var(--middle-column-width); /* Use CSS variable for dynamic width */
}

.middle-column.collapsed {
  padding: 0;
  border-right-width: 0;
}

.middle-column.collapsed > * {
  display: none;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid #e8eaed;
  margin-bottom: 16px;
}

.header h2 {
  margin: 0;
  font-size: 22px; /* 加大字号 */
  font-weight: 600;
  flex-grow: 1;
}

.content {
  flex-grow: 1;
  overflow-y: auto;
}

.section {
  margin-bottom: 24px;
}

.section h3 {
  font-size: 12px;
  color: #5f6368;
  text-transform: none;
  margin-bottom: 8px;
  font-weight: 500;
  padding-left: 8px;
}

.item {
  display: flex;
  align-items: center;
  padding: 8px;
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
}

.item:hover {
  background-color: #f1f3f4;
}

.item.selected {
  background-color: #e8eaf6;
  color: #3f51b5;
}

.arrow {
  margin-right: 12px;
  color: #5f6368;
}

.add-button {
  margin-left: auto;
  font-size: 20px;
  font-weight: 400;
  color: #5f6368;
  cursor: pointer;
}

.toggle-switch {
  margin-left: auto;
  position: relative;
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background-color: #bdc1c6;
  border: none;
  cursor: pointer;
  transition: background-color 0.2s ease-in-out;
  padding: 0;
  display: inline-flex;
  align-items: center;
}

.toggle-switch.is-active {
  background-color: #8ab4f8;
}

.toggle-knob {
  position: absolute;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background-color: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  transition: transform 0.2s ease-in-out;
}

.toggle-switch.is-active .toggle-knob {
  transform: translateX(20px);
}

.uniform-textarea {
  width: 100%;
  height: 32px; /* Fixed height */
  padding: 6px 8px;
  font-family: inherit;
  font-size: 12px;
  border: 1px solid #dadce0; /* Consistent gray border */
  border-radius: 8px;
  resize: none;
  box-sizing: border-box;
  margin-top: 2px;
  margin-bottom: 6px;
}

.uniform-textarea:focus {
  outline: none;
}

.time-range-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  margin-bottom: 6px;
}

.time-range-picker span {
  color: #5f6368;
}
</style>

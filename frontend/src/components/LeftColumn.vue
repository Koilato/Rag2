<template>
  <div class="left-column">
    <div class="header">
      <h2>历史会话</h2>
    </div>
    <div class="content">
      <!-- Upload Section -->
      <div class="upload-section">
        <h3>上传漏洞报告</h3>
        <input type="file" @change="onFileSelected" accept=".csv" />
        <button @click="uploadFile" :disabled="!selectedFile || isLoading">
          {{ isLoading ? '上传中...' : '上传' }}
        </button>
        <p v-if="uploadMessage" :class="{'upload-success': isSuccess, 'upload-error': !isSuccess}">
          {{ uploadMessage }}
        </p>
      </div>
      <!-- History Section can be added below -->
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps } from 'vue';

const props = defineProps({
  username: {
    type: String,
    required: true
  }
});

const selectedFile = ref(null);
const isLoading = ref(false);
const uploadMessage = ref('');
const isSuccess = ref(false);

const onFileSelected = (event) => {
  selectedFile.value = event.target.files[0];
  uploadMessage.value = ''; // Reset message when a new file is selected
};

const uploadFile = async () => {
  if (!selectedFile.value) {
    uploadMessage.value = '请先选择一个文件。';
    isSuccess.value = false;
    return;
  }

  isLoading.value = true;
  uploadMessage.value = '';

  const formData = new FormData();
  formData.append('file', selectedFile.value);
  // 使用 username 作为 db_name, table_name, 和 collection_name
  formData.append('db_name', props.username);
  // 为了简化，我们使用 username 和当前日期组合作为表名
  const tableName = `${props.username}_${new Date().toISOString().split('T')[0].replace(/-/g, '_')}`;
  formData.append('table_name', tableName);
  formData.append('collection_name', props.username);

  try {
    const response = await fetch('http://localhost:8000/api/upload_csv', {
      method: 'POST',
      body: formData,
    });

    const result = await response.json();

    if (response.ok) {
      uploadMessage.value = result.message || '上传成功！';
      isSuccess.value = true;
    } else {
      throw new Error(result.detail || '上传失败。');
    }
  } catch (error) {
    uploadMessage.value = `上传出错: ${error.message}`;
    isSuccess.value = false;
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
.left-column {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: 16px;
  background-color: #F7F7FA;
  border-right: 1px solid #e8eaed;
  overflow: hidden;
  flex-basis: var(--left-column-width); /* Use CSS variable for dynamic width */
}

.upload-section {
  margin-top: 20px;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background-color: #fff;
}

.upload-section h3 {
  margin-top: 0;
}

.upload-section input[type="file"] {
  margin-bottom: 10px;
}

.upload-section button {
  padding: 8px 12px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.upload-section button:disabled {
  background-color: #ccc;
}

.upload-success {
  color: green;
}

.upload-error {
  color: red;
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

.left-column .content p {
  color: #202124;
  font-size: 14px;
  text-align: left;
}
</style>

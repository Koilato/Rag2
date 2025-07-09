<template>
  <div class="right-column">
    <!-- 右侧内容 -->
    <div class="header">
      <h2>会话</h2>
      <div class="icons">
        <span class="icon settings-icon" @click="$emit('export-report')"></span>
      </div>
    </div>
    <div class="content chat-history-container">
      <div v-for="(msg, index) in chatHistory" :key="index" :class="['chat-message', msg.type]">
        <div class="message-bubble">
          {{ msg.message }}
        </div>
      </div>
    </div>
    <div class="footer">
      <div class="input-wrapper">
        <textarea placeholder="发送信息..." class="message-input" ref="messageInput" rows="1" v-model="messageContent"></textarea>
        <img src="../assets/plus.svg" alt="Add" class="add-icon" />
      </div>
      <img src="../assets/up-arrow.svg" alt="Send" class="send-arrow-icon" @click="submit" />
    </div>
  </div>
</template>

<style scoped>
.chat-history-container {
  flex-grow: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
}

.chat-message {
  display: flex;
  margin-bottom: 10px;
}

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.bot {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 70%;
  padding: 10px 15px;
  border-radius: 18px;
  word-wrap: break-word;
  font-size: 14px;
}

.chat-message.user .message-bubble {
  background-color: #e2f0fe;
  color: #333;
}

.chat-message.bot .message-bubble {
  background-color: #f1f1f1;
  color: #333;
}
</style>

<script setup>

import { ref, watch, nextTick } from 'vue'; // Added defineProps
import { processData } from '../utils.js'; // 导入 processData 函数

const emit = defineEmits(['submit', 'export-report']);

// Define props to receive parameters from parent component
const props = defineProps({
  username: {
    type: String,
    required: true
  },
  cve: String,
  uuid: String,
  host: String,
  startDate: String,
  endDate: String,
  autoExportReport: Boolean,
  webSearch: Boolean,
  pluginId: String,
  risk: String,
  protocol: String
});

const messageInput = ref(null);
const messageContent = ref('');
const chatHistory = ref([]); // To store chat messages and responses

const submit = async () => {
  if (!messageContent.value.trim()) {
    return; // Don't send empty messages
  }

  const userMessage = messageContent.value;
  chatHistory.value.push({ type: 'user', message: userMessage }); // Add user message to history
  messageContent.value = ''; // Clear input field

  // Helper function to convert comma-separated strings to an array of strings.
  // Handles null/empty strings and trims whitespace. Returns null for empty input.
  const splitStringToArray = (str) => {
    if (!str) return null;
    const arr = str.split(',').map(item => item.trim()).filter(item => item);
    return arr.length > 0 ? arr : null;
  };

  const paramsToSend = {
    db_name: props.username,
    collection_name: props.username,
    cve: splitStringToArray(props.cve),
    uuid: splitStringToArray(props.uuid),
    host: splitStringToArray(props.host),
    plugin_id: splitStringToArray(props.pluginId),
    risk: splitStringToArray(props.risk),
    protocol: splitStringToArray(props.protocol),
    start_date: props.startDate || null,
    end_date: props.endDate || null,
    auto_export_report: props.autoExportReport,
    web_search: props.webSearch,
    chat_message: userMessage
  };

  try {
    const responseData = await processData(paramsToSend);
    console.log('后端响应:', responseData);
    chatHistory.value.push({ type: 'bot', message: responseData.answer || '无应答' }); // Add bot response
  } catch (error) {
    console.error('发送消息失败:', error);
    const errorMessage = error.detail || error.message || '未知错误';
    chatHistory.value.push({ type: 'bot', message: `发送失败: ${errorMessage}` }); // Add error message
  } finally {
    nextTick(() => {
      // Scroll to bottom of chat history
      const chatContent = document.querySelector('.content');
      if (chatContent) {
        chatContent.scrollTop = chatContent.scrollHeight;
      }
    });
  }
};

watch(messageContent, () => {
  nextTick(() => {
    if (messageInput.value) {
      messageInput.value.style.height = 'auto';
      messageInput.value.style.height = messageInput.value.scrollHeight + 'px';
    }
  });
});
</script>

<style scoped>
.right-column {
  flex: 1; /* Takes remaining space */
  background-color: #fff;
  position: relative; /* For footer positioning */
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: 16px;
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

.icons {
  display: flex; /* Make icons a flex container */
  align-items: center;
}

.icons .icon {
  display: inline-block;
  width: 24px;
  height: 24px;
  margin-left: 8px;
  background-color: #f1f3f4;
  border-radius: 4px;
  cursor: pointer;
}

.icons .grid-icon {
  /* Basic grid icon */
  background-image: 
    linear-gradient(to right, #5f6368 2px, transparent 2px),
    linear-gradient(to bottom, #5f6368 2px, transparent 2px);
  background-size: 6px 6px;
  background-position: center;
  background-repeat: repeat;
}

.icons .settings-icon {
  /* Basic settings/sliders icon */
  background-image: 
    linear-gradient(to bottom, #5f6368 2px, transparent 2px),
    linear-gradient(to bottom, #5f6368 2px, transparent 2px),
    linear-gradient(to bottom, #5f6368 2px, transparent 2px);
  background-size: 14px 2px;
  background-position: center 4px, center 10px, center 16px;
  background-repeat: no-repeat;
}

.content {
  flex-grow: 1;
  overflow-y: auto;
}

.footer {
  position: absolute;
  bottom: 40px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 10px 20px 0 20px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 1000px; /* 设定最大长度为 1000px */
  max-width: calc(100% - 100px); /* 确保在小屏幕上不会超出 */
  border: 2px solid #dadce0;
  border-radius: 24px;
  background-color: #fff;
}

.message-input {
  flex-grow: 1;
  padding: 15px 50px 15px 30px; /* Adjust padding to make text appear lower and make space for plus icon */
  border: none;
  background-color: transparent;
  font-size: 16px;
  font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
  outline: none;
  resize: none;
  overflow-y: auto;
  min-height: 36px;
  max-height: 600px;
  line-height: 1.7;
  letter-spacing: 0.5px;
}

.message-input:focus {
  background-color: transparent;
  border-color: transparent;
}

.add-icon {
  position: absolute;
  right: 15px; /* Position relative to the right edge of the input-wrapper */
  top: 50%;
  transform: translateY(-50%);
  width: 45px;
  height: 45px;
  cursor: pointer;
  border-radius: 50%;

  padding: 6px;
  box-sizing: border-box;

}

.send-arrow-icon {
  width: 55px;
  height: 55px;
  margin-left: 08px;
  cursor: pointer;
  border-radius: 50%;

  padding: 6px;
  box-sizing: border-box;

}
</style>

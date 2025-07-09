import { ref } from 'vue'; // 导入 Vue 的 ref 函数，用于创建响应式引用
import axios from 'axios'; // 确保您的Vue项目已安装axios (npm install axios)

/**
 * useFileUpload 组合式函数
 * 处理文件上传逻辑。
 * 提供必要的引用（ref）和函数，用于触发文件输入并处理选定的文件。
 */
export function useFileUpload() {
  const fileInput = ref(null);
  const uploadStatus = ref(''); // 用于显示上传状态

  const triggerFileUpload = () => {
    if (fileInput.value) {
      fileInput.value.click();
    }
  };

  const handleFileSelected = async (event) => {
    const file = event.target.files[0];
    if (file) {
      console.log('通过组合式函数选择的文件:', file.name);
      uploadStatus.value = '正在上传...';

      const formData = new FormData();
      formData.append('file', file); // 'file' 必须与后端FastAPI的参数名一致

      try {
        const response = await axios.post('http://localhost:8000/api/upload_csv', formData, {
          headers: {
            'Content-Type': 'multipart/form-data', // 必须设置此头部
          },
        });
        console.log('文件上传成功:', response.data);
        uploadStatus.value = `上传成功: ${response.data.filename}`;
        // 可以在这里添加成功后的逻辑，例如刷新数据列表
      } catch (error) {
        console.error('文件上传失败:', error.response ? error.response.data : error.message);
        uploadStatus.value = `上传失败: ${error.response ? error.response.data.detail : error.message}`;
      }
    }
  };

  return {
    fileInput,
    triggerFileUpload,
    handleFileSelected,
    uploadStatus // 暴露上传状态
  };
}

/**
 * exportReport 函数
 * 根据给定的参数从后端生成报告内容，并触发文件下载。
 * @param {object} params - 包含报告所需参数的对象。
 * @param {string} [params.cve] - CVE 信息。
 * @param {string} [params.uuid] - UUID 信息。
 * @param {string} [params.host] - 主机信息。
 * @param {string} [params.start_date] - 时间范围的开始时间 (YYYY-MM-DD)。
 * @param {string} [params.end_date] - 时间范围的结束时间 (YYYY-MM-DD)。
 * @param {boolean} [params.auto_export_report] - 是否自动导出报告。
 * @param {boolean} [params.web_search] - 是否开启联网搜索。
 * @param {string} [params.chat_message] - 会话消息。
 */
export async function exportReport(params) {
  try {
    const response = await axios.post('http://localhost:8000/api/export_report', params, {
      responseType: 'blob', // 关键：告诉axios响应是二进制数据
    });

    // 从响应头中获取文件名，如果后端提供了
    const contentDisposition = response.headers['content-disposition'];
    let filename = `report-${Date.now()}.docx`; // 默认文件名
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="(.+)"/);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1];
      }
    }

    // 创建一个 Blob 对象
    const blob = new Blob([response.data], { type: response.headers['content-type'] });
    // 创建一个临时的 URL
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename; // 设置下载文件名
    document.body.appendChild(link);
    link.click(); // 模拟点击下载
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href); // 释放URL

    console.log('报告下载成功！');
  } catch (error) {
    console.error('报告下载失败:', error.response ? error.response.data : error.message);
    // 可以根据需要显示错误信息给用户
    alert(`报告下载失败: ${error.response ? error.response.data.detail : error.message}`);
  }
}

/**
 * processData 函数
 * 将用户输入和参数发送到后端进行处理。
 * @param {object} params - 包含所有需要发送到后端的数据的对象。
 * @returns {Promise<object>} - 包含后端响应的 Promise。
 */
export async function processData(params) {
  try {
    const response = await axios.post('http://localhost:8000/api/process_data', params);
    return response.data;
  } catch (error) {
    console.error('处理数据失败:', error.response ? error.response.data : error.message);
    // 抛出错误，以便调用方可以捕获它
    throw error.response ? error.response.data : new Error(error.message);
  }
}

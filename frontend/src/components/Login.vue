<template>
  <div class="auth-container">
    <h2>登录</h2>
    <form @submit.prevent="login">
      <div class="form-group">
        <label for="username">用户名:</label>
        <input type="text" id="username" v-model="username" required />
      </div>
      <div class="form-group">
        <label for="password">密码:</label>
        <input type="password" id="password" v-model="password" required />
      </div>
      <button type="submit">登录</button>
      <p v-if="error" class="error-message">{{ error }}</p>
    </form>
    <p class="switch-link">
      还没有账号？<a @click="$emit('switch-to-register')">注册</a>
    </p>
  </div>
</template>

<script>
import { ref } from 'vue';

export default {
  setup(props, { emit }) {
    const username = ref('');
    const password = ref('');
    const error = ref('');

    const login = async () => {
      error.value = ''; // 重置错误信息
      try {
        const response = await fetch('http://localhost:8000/api/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            username: username.value,
            password: password.value,
          }),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          // 登录成功，发出事件并传递用户名
          emit('login-success', username.value);
        } else {
          // 显示后端返回的错误信息
          error.value = data.message || '登录失败，请重试。';
        }
      } catch (e) {
        console.error('Login request failed:', e);
        error.value = '无法连接到服务器，请稍后再试。';
      }
    };

    return {
      username,
      password,
      error,
      login,
    };
  },
};
</script>

<style scoped>
.auth-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background-color: #f0f2f5;
  font-family: Arial, sans-serif;
}

h2 {
  color: #333;
  margin-bottom: 20px;
}

form {
  background-color: #fff;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
  width: 300px;
  text-align: center;
}

.form-group {
  margin-bottom: 15px;
  text-align: left;
}

label {
  display: block;
  margin-bottom: 5px;
  color: #555;
  font-weight: bold;
}

input[type="text"],
input[type="password"] {
  width: calc(100% - 20px);
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}

button {
  width: 100%;
  padding: 10px 15px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 18px;
  cursor: pointer;
  transition: background-color 0.3s ease;
  margin-top: 10px;
}

button:hover {
  background-color: #0056b3;
}

.error-message {
  color: red;
  margin-top: 10px;
  font-size: 14px;
}

.switch-link {
  margin-top: 20px;
  color: #666;
}

.switch-link a {
  color: #007bff;
  text-decoration: none;
  cursor: pointer;
}

.switch-link a:hover {
  text-decoration: underline;
}
</style>

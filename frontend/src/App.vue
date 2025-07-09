<script setup>
import { ref } from 'vue';
import TopHeader from './components/TopHeader.vue';
import ThreeColumnLayout from './components/ThreeColumnLayout.vue';
import Login from './components/Login.vue';

const isLoggedIn = ref(false);
const loggedInUser = ref('');

// 登录成功后的处理函数
const handleLoginSuccess = (username) => {
  isLoggedIn.value = true;
  loggedInUser.value = username;
  // 可选：将用户名存储在 sessionStorage 或 localStorage 中以实现持久登录
  sessionStorage.setItem('loggedInUser', username);
};

// 检查会话中是否已有登录状态
const checkSession = () => {
  const user = sessionStorage.getItem('loggedInUser');
  if (user) {
    isLoggedIn.value = true;
    loggedInUser.value = user;
  }
};

// 组件挂载时检查会话
import { onMounted } from 'vue';
onMounted(() => {
  checkSession();
});

</script>

<template>
  <div id="main-container">
    <template v-if="isLoggedIn">
      <TopHeader />
      <ThreeColumnLayout :username="loggedInUser" />
    </template>
    <template v-else>
      <Login @login-success="handleLoginSuccess" />
    </template>
  </div>
</template>

<style>
body {
  margin: 0;
  padding: 0;
  overflow: hidden;
}

#main-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

#app {
  height: 100%;
}
</style>

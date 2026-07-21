import { Spin } from "antd";
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth } from "./app/RequireAuth";
import { MainLayout } from "./app/MainLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { useAuthStore } from "./features/auth/authStore";
import { ChatPage } from "./features/chat/ChatPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { PlaceholderPage } from "./features/dashboard/PlaceholderPage";
import { KnowledgePage } from "./features/knowledge/KnowledgePage";

function App() {
  const { initialized, initialize } = useAuthStore();

  useEffect(() => {
    void initialize();
  }, [initialize]);

  if (!initialized) {
    return (
      <div className="route-loader" aria-label="正在加载">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<MainLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route
            path="memory"
            element={<PlaceholderPage title="记忆图谱" description="Neo4j 记忆提取与图谱即将接入" />}
          />
          <Route
            path="search"
            element={<PlaceholderPage title="全局搜索" description="文档、图片与记忆搜索即将接入" />}
          />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;

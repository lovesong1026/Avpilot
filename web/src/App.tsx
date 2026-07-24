import { Spin } from "antd";
import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth } from "./app/RequireAuth";
import { MainLayout } from "./app/MainLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { useAuthStore } from "./features/auth/authStore";

const ChatPage = lazy(() => import("./features/chat/ChatPage").then((module) => ({ default: module.ChatPage })));
const DashboardPage = lazy(() => import("./features/dashboard/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const ImageLibraryPage = lazy(() => import("./features/images/ImageLibraryPage").then((module) => ({ default: module.ImageLibraryPage })));
const KnowledgePage = lazy(() => import("./features/knowledge/KnowledgePage").then((module) => ({ default: module.KnowledgePage })));
const MemoryPage = lazy(() => import("./features/memory/MemoryPage").then((module) => ({ default: module.MemoryPage })));
const ResearchPage = lazy(() => import("./features/research/ResearchPage").then((module) => ({ default: module.ResearchPage })));
const SearchPage = lazy(() => import("./features/search/SearchPage").then((module) => ({ default: module.SearchPage })));

function page(content: ReactNode) {
  return <Suspense fallback={<div className="route-loader"><Spin size="large" /></div>}>{content}</Suspense>;
}

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
          <Route index element={page(<DashboardPage />)} />
          <Route path="knowledge" element={page(<KnowledgePage />)} />
          <Route path="images" element={page(<ImageLibraryPage />)} />
          <Route path="chat" element={page(<ChatPage />)} />
          <Route path="research" element={page(<ResearchPage />)} />
          <Route path="memory" element={page(<MemoryPage />)} />
          <Route path="search" element={page(<SearchPage />)} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;

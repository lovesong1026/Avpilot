import {
  BookOutlined,
  CommentOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  NodeIndexOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Layout, Menu, Space, Typography } from "antd";
import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuthStore } from "../features/auth/authStore";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/", icon: <DatabaseOutlined />, label: "工作台" },
  { key: "/knowledge", icon: <BookOutlined />, label: "知识库" },
  { key: "/chat", icon: <CommentOutlined />, label: "智能问答" },
  { key: "/memory", icon: <NodeIndexOutlined />, label: "记忆图谱" },
  { key: "/search", icon: <SearchOutlined />, label: "全局搜索" },
];

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <Layout className="app-layout">
      <Sider
        className="app-sider"
        collapsed={collapsed}
        collapsedWidth={76}
        width={244}
        breakpoint="lg"
        onBreakpoint={setCollapsed}
      >
        <button className="brand" type="button" onClick={() => navigate("/")}>
          <span className="brand-mark">A</span>
          {!collapsed && (
            <span className="brand-copy">
              <strong>Avpilot</strong>
              <small>星航仪</small>
            </span>
          )}
        </button>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
        <div className="sider-foot">
          {!collapsed && <span>你的 AI 知识领航系统</span>}
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <Button
            type="text"
            aria-label={collapsed ? "展开菜单" : "收起菜单"}
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed((value) => !value)}
          />
          <Space size="middle">
            <Avatar className="user-avatar">
              {(user?.display_name || user?.username || "A").slice(0, 1).toUpperCase()}
            </Avatar>
            <div className="user-copy">
              <Typography.Text strong>{user?.display_name || user?.username}</Typography.Text>
              <Typography.Text type="secondary">{user?.email}</Typography.Text>
            </div>
            <Button type="text" icon={<LogoutOutlined />} onClick={() => void handleLogout()}>
              退出
            </Button>
          </Space>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

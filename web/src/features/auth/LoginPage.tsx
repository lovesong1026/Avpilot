import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { Alert, App, Button, Form, Input } from "antd";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import type { LoginInput } from "../../entities/auth";
import { apiErrorMessage } from "../../shared/apiClient";
import { AuthShell } from "./AuthShell";
import { useAuthStore } from "./authStore";

export function LoginPage() {
  const { message } = App.useApp();
  const [error, setError] = useState("");
  const location = useLocation();
  const navigate = useNavigate();
  const { user, loading, login } = useAuthStore();

  if (user) return <Navigate to="/" replace />;

  const handleSubmit = async (values: LoginInput) => {
    setError("");
    try {
      await login(values);
      message.success("登录成功");
      const destination = (location.state as { from?: string } | null)?.from ?? "/";
      navigate(destination, { replace: true });
    } catch (requestError) {
      setError(apiErrorMessage(requestError, "登录失败，请检查账号和密码"));
    }
  };

  return (
    <AuthShell eyebrow="欢迎回来" title="登录 Avpilot" description="继续探索课题组的知识与记忆。">
      {error && <Alert className="auth-alert" type="error" showIcon message={error} />}
      <Form<LoginInput> layout="vertical" size="large" onFinish={handleSubmit} requiredMark={false}>
        <Form.Item label="用户名或邮箱" name="identifier" rules={[{ required: true, message: "请输入用户名或邮箱" }]}>
          <Input prefix={<UserOutlined />} placeholder="username@example.com" autoComplete="username" />
        </Form.Item>
        <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
          <Input.Password prefix={<LockOutlined />} placeholder="输入密码" autoComplete="current-password" />
        </Form.Item>
        <Button className="auth-submit" type="primary" htmlType="submit" loading={loading} block>
          登录
        </Button>
      </Form>
      <p className="auth-switch">还没有账号？<Link to="/register">创建账号</Link></p>
    </AuthShell>
  );
}

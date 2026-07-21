import { LockOutlined, MailOutlined, SmileOutlined, UserOutlined } from "@ant-design/icons";
import { Alert, App, Button, Form, Input } from "antd";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import type { RegisterInput } from "../../entities/auth";
import { apiErrorMessage } from "../../shared/apiClient";
import { AuthShell } from "./AuthShell";
import { useAuthStore } from "./authStore";

type RegisterForm = RegisterInput & { confirm_password: string };

export function RegisterPage() {
  const { message } = App.useApp();
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { user, loading, register } = useAuthStore();

  if (user) return <Navigate to="/" replace />;

  const handleSubmit = async ({ confirm_password: _, ...values }: RegisterForm) => {
    setError("");
    try {
      await register(values);
      message.success("账号创建成功");
      navigate("/", { replace: true });
    } catch (requestError) {
      setError(apiErrorMessage(requestError, "注册失败，请稍后重试"));
    }
  };

  return (
    <AuthShell eyebrow="加入 Avpilot" title="创建账号" description="创建你的默认知识库，从第一份资料开始。">
      {error && <Alert className="auth-alert" type="error" showIcon message={error} />}
      <Form<RegisterForm> layout="vertical" size="large" onFinish={handleSubmit} requiredMark={false}>
        <div className="form-grid">
          <Form.Item label="用户名" name="username" rules={[{ required: true }, { min: 3, message: "至少 3 个字符" }, { pattern: /^[A-Za-z0-9_]+$/, message: "仅支持字母、数字和下划线" }]}>
            <Input prefix={<UserOutlined />} placeholder="avp_member" autoComplete="username" />
          </Form.Item>
          <Form.Item label="显示名称" name="display_name">
            <Input prefix={<SmileOutlined />} placeholder="你的称呼" />
          </Form.Item>
        </div>
        <Form.Item label="邮箱" name="email" rules={[{ required: true }, { type: "email", message: "请输入有效邮箱" }]}>
          <Input prefix={<MailOutlined />} placeholder="name@example.com" autoComplete="email" />
        </Form.Item>
        <Form.Item label="密码" name="password" rules={[{ required: true }, { min: 8, message: "至少 8 个字符" }]}>
          <Input.Password prefix={<LockOutlined />} placeholder="至少 8 个字符" autoComplete="new-password" />
        </Form.Item>
        <Form.Item label="确认密码" name="confirm_password" dependencies={["password"]} rules={[{ required: true }, ({ getFieldValue }) => ({ validator(_, value) { return !value || getFieldValue("password") === value ? Promise.resolve() : Promise.reject(new Error("两次输入的密码不一致")); } })]}>
          <Input.Password prefix={<LockOutlined />} placeholder="再次输入密码" autoComplete="new-password" />
        </Form.Item>
        <Button className="auth-submit" type="primary" htmlType="submit" loading={loading} block>
          创建账号
        </Button>
      </Form>
      <p className="auth-switch">已有账号？<Link to="/login">直接登录</Link></p>
    </AuthShell>
  );
}

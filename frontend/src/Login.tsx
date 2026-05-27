import { useState } from "react";
import { Button, Card, Form, Input, Typography, message } from "antd";
import { LockOutlined, MailOutlined, UserOutlined } from "@ant-design/icons";
import { login } from "./api";

interface Props {
  onSuccess: () => void;
}

export default function Login({ onSuccess }: Props) {
  const [loading, setLoading] = useState(false);

  const handleFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const { access_token } = await login(values.username, values.password);
      localStorage.setItem("auth_token", access_token);
      onSuccess();
    } catch {
      message.error("用户名或密码错误");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", background: "#f5f5f5",
    }}>
      <Card style={{ width: 380, boxShadow: "0 4px 24px rgba(0,0,0,0.08)" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12, margin: "0 auto 16px",
            background: "linear-gradient(135deg, #1677ff 0%, #0958d9 100%)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <MailOutlined style={{ color: "#fff", fontSize: 22 }} />
          </div>
          <Typography.Title level={4} style={{ marginBottom: 4 }}>邮件追踪系统</Typography.Title>
          <Typography.Text type="secondary">请登录以继续</Typography.Text>
        </div>

        <Form onFinish={handleFinish} layout="vertical" requiredMark={false}>
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined style={{ color: "#bfbfbf" }} />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined style={{ color: "#bfbfbf" }} />} placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
            <Button type="primary" htmlType="submit" block size="large" loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}

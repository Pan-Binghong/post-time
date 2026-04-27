import { useCallback, useEffect, useState } from "react";
import {
  Alert, Button, Card, Form, Input, Popconfirm,
  Space, Table, Tag, Typography, message,
} from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { fetchCredentialList, saveCredentials, deleteCredential } from "./api";
import type { CredentialItem } from "./types";

const { Title, Text } = Typography;

export default function Settings() {
  const [credentials, setCredentials] = useState<CredentialItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const [msg, msgCtx] = message.useMessage();

  const load = useCallback(() => {
    setLoading(true);
    fetchCredentialList()
      .then(setCredentials)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async (values: { email: string; smtpCode: string }) => {
    setSaving(true);
    try {
      await saveCredentials(values.email.trim(), values.smtpCode.trim());
      msg.success("认证成功，凭据已保存");
      form.resetFields();
      load();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      msg.error(e?.response?.data?.detail || "保存失败，请检查邮箱和授权码");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteCredential(id);
      msg.success("已删除");
      load();
    } catch {
      msg.error("删除失败");
    }
  };

  const columns: ColumnsType<CredentialItem> = [
    {
      title: "邮箱地址", dataIndex: "email",
      render: v => <Text code>{v}</Text>,
    },
    {
      title: "SMTP 授权码", dataIndex: "smtp_code_masked",
      render: v => <Tag color="default">{v}</Tag>,
    },
    {
      title: "操作", width: 80,
      render: (_, c) => (
        <Popconfirm title="确认删除此凭据？" okText="删除" cancelText="取消" okButtonProps={{ danger: true }} onConfirm={() => handleDelete(c.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <>
      {msgCtx}
      <Title level={4} style={{ marginBottom: 6 }}>系统设置</Title>
      <Text type="secondary" style={{ display: "block", marginBottom: 24 }}>
        管理 SMTP 发件凭据，创建任务时可选择指定发件人。
      </Text>

      <Card
        title="SMTP 发件凭据"
        extra={<Text type="secondary" style={{ fontSize: 12 }}>共 {credentials.length} 组</Text>}
        style={{ marginBottom: 20 }}
        loading={loading}
      >
        <Table
          columns={columns}
          dataSource={credentials}
          rowKey="id"
          size="small"
          pagination={false}
          locale={{ emptyText: "暂无凭据，请在下方添加" }}
        />
      </Card>

      <Card title={<Space><PlusOutlined />添加 SMTP 凭据</Space>} style={{ maxWidth: 500 }}>
        <Alert
          message="如何获取 SMTP 授权码"
          description="登录 163 企业邮箱 → 设置 → POP3/SMTP/IMAP → 开启 SMTP 服务 → 获取授权码"
          type="info" showIcon style={{ marginBottom: 20 }}
        />
        <Form form={form} layout="vertical" onFinish={handleAdd}>
          <Form.Item name="email" label="邮箱地址" rules={[{ required: true, type: "email", message: "请输入有效邮箱" }]}>
            <Input placeholder="user@company.163.com" />
          </Form.Item>
          <Form.Item name="smtpCode" label="SMTP 授权码" rules={[{ required: true, message: "请输入 SMTP 授权码" }]}>
            <Input.Password placeholder="输入 SMTP 授权码" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={saving} icon={<PlusOutlined />}>
              验证并添加
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </>
  );
}

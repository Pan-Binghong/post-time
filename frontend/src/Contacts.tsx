import { useCallback, useEffect, useState } from "react";
import {
  Button, Card, Form, Input, Modal, Popconfirm, Space,
  Table, Tag, Typography, message,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { fetchContacts, createContact, updateContact, deleteContact } from "./api";
import type { ContactItem } from "./types";

const { Title, Text } = Typography;

export default function Contacts({ onBack: _onBack }: { onBack?: () => void }) {
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<ContactItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [form] = Form.useForm();
  const [msg, msgCtx] = message.useMessage();

  const load = useCallback(() => {
    setLoading(true);
    fetchContacts().then(setContacts).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const openAdd = () => { setEditItem(null); form.resetFields(); setModalOpen(true); };
  const openEdit = (c: ContactItem) => {
    setEditItem(c);
    form.setFieldsValue({ name: c.name, email: c.email, department: c.department, business_unit: c.business_unit, location: c.location });
    setModalOpen(true);
  };

  const handleSave = async (values: { name: string; email: string; department: string; business_unit: string; location: string }) => {
    setSaving(true);
    try {
      if (editItem) {
        await updateContact(editItem.id, values);
        msg.success("联系人已更新");
      } else {
        await createContact(values);
        msg.success("联系人已添加");
      }
      setModalOpen(false);
      load();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      msg.error(e?.response?.data?.detail || "操作失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    await deleteContact(id);
    msg.success("已删除");
    load();
  };

  const filtered = contacts.filter((c) => {
    const q = search.toLowerCase();
    return !q || [c.name, c.email, c.department, c.business_unit, c.location].some((f) => f?.toLowerCase().includes(q));
  });

  const columns: ColumnsType<ContactItem> = [
    { title: "姓名", dataIndex: "name", width: 100, render: (v) => <Text strong>{v}</Text> },
    { title: "邮箱", dataIndex: "email", width: 220, render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text> },
    { title: "部门", dataIndex: "department", width: 120, render: (v) => v || <Text type="secondary">—</Text> },
    { title: "事业部", dataIndex: "business_unit", width: 130, render: (v) => v || <Text type="secondary">—</Text> },
    {
      title: "地点", dataIndex: "location", width: 100,
      render: (v) => v ? <Tag color="blue">{v}</Tag> : <Text type="secondary">—</Text>,
    },
    {
      title: "操作", width: 120, fixed: "right",
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm
            title="确定删除该联系人？"
            description="关联的任务收件人配置也会被删除。"
            onConfirm={() => handleDelete(record.id)}
            okText="删除" cancelText="取消" okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      {msgCtx}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0 }}>通讯录管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>添加联系人</Button>
      </div>

      <Card>
        <div style={{ marginBottom: 16 }}>
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索姓名、邮箱、部门、事业部、地点…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
            style={{ maxWidth: 360 }}
          />
          <Text type="secondary" style={{ marginLeft: 12, fontSize: 12 }}>
            共 {contacts.length} 位{search ? `，匹配 ${filtered.length} 位` : ""}
          </Text>
        </div>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 20, showSizeChanger: false, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ x: 700 }}
        />
      </Card>

      <Modal
        title={editItem ? "编辑联系人" : "添加联系人"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        destroyOnHidden
        width={540}
      >
        <Form form={form} layout="vertical" onFinish={handleSave} style={{ marginTop: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
            <Form.Item name="name" label="姓名" rules={[{ required: true, message: "请输入姓名" }]}>
              <Input placeholder="张慧" />
            </Form.Item>
            <Form.Item name="email" label="邮箱" rules={[{ required: true, type: "email", message: "请输入有效邮箱" }]}>
              <Input placeholder="zhanghui@example.com" />
            </Form.Item>
            <Form.Item name="department" label="部门">
              <Input placeholder="研发部" />
            </Form.Item>
            <Form.Item name="business_unit" label="事业部">
              <Input placeholder="化学事业部" />
            </Form.Item>
            <Form.Item
              name="location"
              label="地点"
              extra="决定邮件标题中的【XX】标识"
            >
              <Input placeholder="烟台 / 上海 / 重庆" />
            </Form.Item>
          </div>
          <Form.Item style={{ marginBottom: 0, textAlign: "right" }}>
            <Space>
              <Button onClick={() => setModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={saving}>
                {editItem ? "更新" : "添加"}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Button, Card, Col, Form, Input, Modal, Popconfirm,
  Row, Select, Space, Table, Tag, Tooltip, Typography, message,
} from "antd";
import {
  BoldOutlined, DeleteOutlined, EditOutlined,
  FontColorsOutlined, PlusOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  fetchTaskTypes, createTaskType, updateTaskType, deleteTaskType,
  fetchTemplates, createTemplate, updateTemplate, deleteTemplate,
} from "./api";
import type { TaskTypeItem, TemplateItem } from "./types";
import AiChatPanel from "./AiChatPanel";
import RichTextEditor, { type RichTextEditorHandle } from "./RichTextEditor";
import { PLACEHOLDER_META } from "./HighlightedTextarea";

const { Text } = Typography;

const BUILTIN_NAMES = new Set(["按季度发送文档收集", "按季度发送数据统计支持"]);


export default function CustomTaskTypes({
  onConfigureTask,
}: {
  onConfigureTask?: (id: number, name: string) => void;
}) {
  const [taskTypes, setTaskTypes] = useState<TaskTypeItem[]>([]);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [msg, msgCtx] = message.useMessage();

  // ── TaskType modal
  const [ttModalOpen, setTtModalOpen] = useState(false);
  const [ttEditing, setTtEditing] = useState<TaskTypeItem | null>(null);
  const [ttForm] = Form.useForm();

  // ── Template modal
  const [tmplModalOpen, setTmplModalOpen] = useState(false);
  const [tmplEditing, setTmplEditing] = useState<TemplateItem | null>(null);
  const [tmplForm] = Form.useForm();
  const [bodyValue, setBodyValue] = useState("");
  const editorRef = useRef<RichTextEditorHandle | null>(null);

  const load = useCallback(() => {
    fetchTaskTypes().then(setTaskTypes).catch(() => {});
    fetchTemplates().then(setTemplates).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  // ── TaskType handlers ────────────────────────────────────────
  const openCreateTt = () => { setTtEditing(null); ttForm.resetFields(); setTtModalOpen(true); };
  const openEditTt = (tt: TaskTypeItem) => {
    setTtEditing(tt);
    ttForm.setFieldsValue({ name: tt.name, description: tt.description, template_id: tt.template_id });
    setTtModalOpen(true);
  };
  const handleSaveTt = async () => {
    const values = await ttForm.validateFields();
    try {
      ttEditing ? await updateTaskType(ttEditing.id, values) : await createTaskType(values);
      msg.success(ttEditing ? "已更新" : "已创建");
      setTtModalOpen(false); load();
    } catch { msg.error("保存失败"); }
  };
  const handleDeleteTt = async (id: number) => {
    try { await deleteTaskType(id); msg.success("已删除"); load(); }
    catch { msg.error("删除失败，请先删除该类型下的收件人和任务"); }
  };

  // ── Template handlers ────────────────────────────────────────
  const openCreateTmpl = () => {
    setTmplEditing(null); tmplForm.resetFields();
    setBodyValue(""); setTmplModalOpen(true);
  };
  const openEditTmpl = (t: TemplateItem) => {
    setTmplEditing(t);
    tmplForm.setFieldsValue({ name: t.name, subject: t.subject });
    setBodyValue(t.body); setTmplModalOpen(true);
  };
  const handleSaveTmpl = async () => {
    const values = await tmplForm.validateFields();
    const payload = { ...values, body: bodyValue };
    if (!bodyValue.trim()) { msg.warning("请输入正文"); return; }
    try {
      tmplEditing ? await updateTemplate(tmplEditing.id, payload) : await createTemplate(payload);
      msg.success(tmplEditing ? "已更新" : "已创建");
      setTmplModalOpen(false);
      load();
    } catch { msg.error("保存失败"); }
  };
  const handleDeleteTmpl = async (id: number) => {
    try { await deleteTemplate(id); msg.success("已删除"); load(); }
    catch { msg.error("删除失败"); }
  };

  // ── 格式工具：通过 execCommand 操作富文本编辑器 ──────────────
  const execFormat = (cmd: string, val?: string) => editorRef.current?.execCmd(cmd, val);
  const insertPlaceholder = (label: string) => editorRef.current?.insertText(label);

  // ── Tables ────────────────────────────────────────────────────
  const ttColumns: ColumnsType<TaskTypeItem> = [
    { title: "任务名称", dataIndex: "name", render: v => <Text strong>{v}</Text> },
    { title: "描述", dataIndex: "description", render: v => <Text type="secondary">{v || "—"}</Text> },
    {
      title: "邮件模板", dataIndex: "template_id", width: 160,
      render: id => { const t = templates.find(t => t.id === id); return t ? <Text code>{t.name}</Text> : <Text type="secondary">—</Text>; },
    },
    {
      title: "操作", width: 200,
      render: (_, tt) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditTt(tt)}>编辑</Button>
          <Button size="small" type="primary" onClick={() => onConfigureTask?.(tt.id, tt.name)}>配置</Button>
          {!BUILTIN_NAMES.has(tt.name) && (
            <Popconfirm title="确认删除此任务类型？" okText="删除" cancelText="取消" okButtonProps={{ danger: true }} onConfirm={() => handleDeleteTt(tt.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  const tmplColumns: ColumnsType<TemplateItem> = [
    { title: "模板名称", dataIndex: "name", render: v => <Text strong>{v}</Text> },
    { title: "主题", dataIndex: "subject", render: v => <Text code style={{ fontSize: 12 }}>{v}</Text> },
    {
      title: "操作", width: 160,
      render: (_, t) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditTmpl(t)}>编辑</Button>
          <Popconfirm title="确认删除此模板？" okText="删除" cancelText="取消" okButtonProps={{ danger: true }} onConfirm={() => handleDeleteTmpl(t.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      {msgCtx}

      <Card title="任务类型管理" extra={<Button type="primary" icon={<PlusOutlined />} onClick={openCreateTt}>新建任务类型</Button>} style={{ marginBottom: 16 }}>
        <Table columns={ttColumns} dataSource={taskTypes} rowKey="id" size="small" pagination={false} />
      </Card>

      <Card title="邮件模板管理" extra={<Button icon={<PlusOutlined />} onClick={openCreateTmpl}>新建模板</Button>}>
        {/* 占位符图例 */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
          {PLACEHOLDER_META.map(m => (
            <Tag key={m.key} style={{ background: m.bg, color: m.fg, border: `1px solid ${m.fg}33`, borderRadius: 4, fontFamily: "monospace", fontSize: 12, fontWeight: 600, cursor: "default" }}>
              {m.label}
              <span style={{ fontFamily: "sans-serif", fontWeight: 400, color: "#666", marginLeft: 4, fontSize: 11 }}>{m.desc}</span>
            </Tag>
          ))}
        </div>
        <Table columns={tmplColumns} dataSource={templates} rowKey="id" size="small" pagination={false} />
      </Card>

      {/* ── TaskType Modal ── */}
      <Modal title={ttEditing ? "编辑任务类型" : "新建任务类型"} open={ttModalOpen} onOk={handleSaveTt} onCancel={() => setTtModalOpen(false)} okText="保存" cancelText="取消" width={500}>
        <Form form={ttForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="任务名称" rules={[{ required: true, message: "请输入名称" }]}>
            <Input placeholder="如：季度合规邮件" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="简短描述该任务的用途" />
          </Form.Item>
          <Form.Item name="template_id" label="邮件模板">
            <Select allowClear placeholder="选择模板（可选，后续也可在配置页选择）" options={templates.map(t => ({ value: t.id, label: t.name }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Template Modal ── */}
      <Modal
        title={tmplEditing ? "编辑邮件模板" : "新建邮件模板"}
        open={tmplModalOpen}
        onOk={handleSaveTmpl}
        onCancel={() => setTmplModalOpen(false)}
        okText="保存模板"
        cancelText="取消"
        width={1400}
        styles={{ body: { padding: "12px 20px 8px" } }}
      >
        {/* 名称 + 主题 */}
        <Form form={tmplForm} layout="vertical">
          <Row gutter={12}>
            <Col span={6}>
              <Form.Item name="name" label="模板名称" rules={[{ required: true, message: "请输入名称" }]} style={{ marginBottom: 8 }}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={18}>
              <Form.Item name="subject" label="邮件主题" rules={[{ required: true, message: "请输入主题" }]} style={{ marginBottom: 8 }}>
                <Input placeholder="【{{location}}】{{year}}年Q{{quarter}}通知{{send_date}}" />
              </Form.Item>
            </Col>
          </Row>
        </Form>

        <Row gutter={16} style={{ minHeight: 480 }}>
          {/* 左：富文本编辑区 */}
          <Col span={15} style={{ display: "flex", flexDirection: "column", gap: 8 }}>

            {/* 格式工具栏 */}
            <div style={{
              display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap",
              padding: "4px 8px", background: "#f8fafc", borderRadius: 6, border: "1px solid #e2e8f0",
            }}>
              <Tooltip title="加粗"><Button size="small" type="text" icon={<BoldOutlined />} onMouseDown={e => { e.preventDefault(); execFormat("bold"); }} /></Tooltip>
              <Tooltip title="斜体"><Button size="small" type="text" icon={<span style={{ fontStyle: "italic", fontWeight: 600, fontSize: 13 }}>I</span>} onMouseDown={e => { e.preventDefault(); execFormat("italic"); }} /></Tooltip>
              <Tooltip title="下划线"><Button size="small" type="text" icon={<span style={{ textDecoration: "underline", fontSize: 13 }}>U</span>} onMouseDown={e => { e.preventDefault(); execFormat("underline"); }} /></Tooltip>
              <div style={{ width: 1, height: 14, background: "#e2e8f0", margin: "0 2px" }} />
              <Tooltip title="红色文字"><Button size="small" type="text" icon={<FontColorsOutlined style={{ color: "#e03030" }} />} onMouseDown={e => { e.preventDefault(); execFormat("foreColor", "#e03030"); }} /></Tooltip>
              <Tooltip title="蓝色文字"><Button size="small" type="text" icon={<FontColorsOutlined style={{ color: "#1a56db" }} />} onMouseDown={e => { e.preventDefault(); execFormat("foreColor", "#1a56db"); }} /></Tooltip>
              <Tooltip title="橙色文字"><Button size="small" type="text" icon={<FontColorsOutlined style={{ color: "#d46b08" }} />} onMouseDown={e => { e.preventDefault(); execFormat("foreColor", "#d46b08"); }} /></Tooltip>
              <div style={{ width: 1, height: 14, background: "#e2e8f0", margin: "0 2px" }} />
              <Tooltip title="有序列表"><Button size="small" type="text" onMouseDown={e => { e.preventDefault(); execFormat("insertOrderedList"); }}>1.</Button></Tooltip>
              <Tooltip title="无序列表"><Button size="small" type="text" onMouseDown={e => { e.preventDefault(); execFormat("insertUnorderedList"); }}>•</Button></Tooltip>
              <div style={{ flex: 1 }} />
              {/* 占位符插入 */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                {PLACEHOLDER_META.map(m => (
                  <Tooltip key={m.key} title={m.desc}>
                    <Tag
                      onMouseDown={e => { e.preventDefault(); insertPlaceholder(m.label); }}
                      style={{
                        background: m.bg, color: m.fg, border: `1px solid ${m.fg}44`,
                        borderRadius: 4, fontFamily: "monospace", fontSize: 11,
                        fontWeight: 700, cursor: "pointer", margin: 0, padding: "0 5px",
                      }}
                    >
                      {m.label}
                    </Tag>
                  </Tooltip>
                ))}
              </div>
            </div>

            {/* 富文本编辑器 */}
            <RichTextEditor
              ref={editorRef}
              value={bodyValue}
              onChange={setBodyValue}
              placeholder="在此输入邮件正文，可以直接排版编辑…"
              minHeight={360}
            />
          </Col>

          {/* 右：AI 面板 */}
          <Col span={9} style={{
            borderLeft: "1px solid #f0f0f0", paddingLeft: 16,
            display: "flex", flexDirection: "column",
          }}>
            <AiChatPanel
              onApply={(result) => {
                tmplForm.setFieldsValue({ subject: result.subject });
                setBodyValue(result.body.replace(/>\s*[\r\n]+\s*</g, '><').trim());
                msg.success("已应用 AI 生成内容");
              }}
            />
          </Col>
        </Row>
      </Modal>
    </>
  );
}

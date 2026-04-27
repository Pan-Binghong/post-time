import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert, Badge, Button, Card, Col, Collapse, DatePicker, Descriptions,
  Divider, Popconfirm, Row, Select, Space, Spin, Table, Tag, Typography, Upload, message,
} from "antd";
import {
  DeleteOutlined, EyeOutlined, PlusOutlined,
  SendOutlined, ThunderboltOutlined, UploadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import {
  fetchContacts, fetchRecipients, addRecipient, deleteRecipient,
  fetchTasks, createTask, executeTask, deleteTask, previewPatentEmail,
  fetchCredentialList,
} from "./api";
import type { ContactItem, CredentialItem, RecipientItem, TaskItem, PreviewResponse } from "./types";

const { Title, Text } = Typography;

type GroupBy = "location" | "department" | "business_unit";

const GROUP_LABELS: Record<GroupBy, string> = {
  location: "区域", department: "部门", business_unit: "事业部",
};

const TASK_STATUS: Record<string, { color: string; label: string }> = {
  pending:   { color: "default",    label: "待执行" },
  running:   { color: "processing", label: "执行中" },
  completed: { color: "success",    label: "已完成" },
  failed:    { color: "error",      label: "失败"   },
};

interface Props { taskTypeId: number; taskTypeName: string; onBack?: () => void; }

export default function TaskConfig({ taskTypeId, taskTypeName }: Props) {
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [recipients, setRecipients] = useState<RecipientItem[]>([]);
  const [selectedContactIds, setSelectedContactIds] = useState<number[]>([]);
  const [selectedRole, setSelectedRole] = useState<string>("to");

  const [credentials, setCredentials] = useState<CredentialItem[]>([]);
  const [selectedCredentialId, setSelectedCredentialId] = useState<number | null>(null);
  const [groupBy, setGroupBy] = useState<GroupBy>("location");
  const [ipLocation, setIpLocation] = useState<string>("药源");
  const isPatentTask  = taskTypeName === "按季度发送专利素材收集";
  const isIpStatsTask = taskTypeName === "按季度发送知识产权数据统计支持";
  const isBuiltinTask = isPatentTask || isIpStatsTask;
  const [scheduledTimes, setScheduledTimes] = useState<(dayjs.Dayjs | null)[]>([null]);
  const [fileList, setFileList] = useState<{ file: File; name: string }[]>([]);

  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [editTime, setEditTime] = useState<dayjs.Dayjs | null>(null);
  const [msg, msgCtx] = message.useMessage();

  const loadContacts  = useCallback(() => fetchContacts().then(setContacts).catch(() => {}), []);
  const loadCredentials = useCallback(() =>
    fetchCredentialList().then(list => {
      setCredentials(list);
      if (list.length > 0 && selectedCredentialId === null) setSelectedCredentialId(list[0].id);
    }).catch(() => {}),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  []);
  const loadRecipients = useCallback(() => fetchRecipients(taskTypeId).then(setRecipients).catch(() => {}), [taskTypeId]);
  const loadTasks     = useCallback(() =>
    fetchTasks().then((all) => setTasks(all.filter((t) => t.task_type_id === taskTypeId))).catch(() => {}),
    [taskTypeId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadContacts(), loadRecipients(), loadTasks(), loadCredentials()]).finally(() => setLoading(false));
  }, [loadContacts, loadRecipients, loadTasks]);

  const addedIds     = new Set(recipients.map((r) => r.contact_id));
  const available    = contacts.filter((c) => !addedIds.has(c.id));
  const toRecipients = recipients.filter((r) => r.role === "to");
  const ccRecipients = recipients.filter((r) => r.role === "cc");

  const groups = useMemo(() => {
    if (isIpStatsTask) {
      return toRecipients.length > 0 ? { [ipLocation]: toRecipients } : {} as Record<string, RecipientItem[]>;
    }
    if (!isBuiltinTask) {
      // 自定义任务：所有 TO 收件人作为一组，不分组
      return toRecipients.length > 0 ? { "全部": toRecipients } : {} as Record<string, RecipientItem[]>;
    }
    const map: Record<string, RecipientItem[]> = {};
    for (const r of toRecipients) {
      const key = (groupBy === "department" ? r.department : groupBy === "business_unit" ? r.business_unit : r.location) || "未分类";
      (map[key] ??= []).push(r);
    }
    return map;
  }, [toRecipients, groupBy, isIpStatsTask, isBuiltinTask, ipLocation]);
  const groupKeys = Object.keys(groups);

  const handleAddRecipient = async () => {
    if (!selectedContactIds.length) { msg.warning("请选择联系人"); return; }
    let added = 0;
    for (const cid of selectedContactIds) {
      try { await addRecipient(taskTypeId, cid, selectedRole); added++; } catch { /* skip */ }
    }
    setSelectedContactIds([]);
    loadRecipients();
    added > 0 ? msg.success(`已添加 ${added} 人`) : msg.warning("所选联系人已存在");
  };

  const handleDeleteRecipient = async (id: number) => {
    await deleteRecipient(taskTypeId, id);
    loadRecipients();
  };

  const handlePreview = async () => {
    const firstTime = scheduledTimes.find(Boolean);
    try {
      const res = await previewPatentEmail({
        task_type_id: taskTypeId,
        group_by: isIpStatsTask ? ipLocation : groupBy,
        scheduled_time: firstTime ? firstTime.toISOString() : "",
        attachment_names: fileList.map((f) => f.name),
      });
      setPreview(res);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      msg.error(e?.response?.data?.detail || "预览失败");
    }
  };

  const handleCreateTask = async () => {
    const validTimes = scheduledTimes.filter(Boolean) as dayjs.Dayjs[];
    if (!validTimes.length) { msg.warning("请至少设置一个发送时间"); return; }
    if (!groupKeys.length)  { msg.warning("没有可用的分组"); return; }
    const allSchedules = validTimes.flatMap((t) =>
      groupKeys.map((key) => ({ group_key: key, scheduled_time: t.toISOString() }))
    );
    setCreating(true);
    try {
      const fd = new FormData();
      fd.append("task_type_id", String(taskTypeId));
      fd.append("group_schedules", JSON.stringify(allSchedules));
      fd.append("task_config", JSON.stringify({ group_by: groupBy }));
      if (selectedCredentialId) fd.append("credential_id", String(selectedCredentialId));
      fileList.forEach((f) => fd.append("files", f.file));
      await createTask(fd);
      msg.success(`已创建 ${allSchedules.length} 个定时任务`);
      loadTasks();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      msg.error(e?.response?.data?.detail || "创建失败");
    } finally { setCreating(false); }
  };

  const handleExecuteNow = async (taskId: number) => {
    try { await executeTask(taskId); msg.success(`任务 #${taskId} 已执行`); loadTasks(); }
    catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      msg.error(e?.response?.data?.detail || "执行失败");
    }
  };

  const handleDeleteTask = async (taskId: number) => {
    try {
      await deleteTask(taskId);
      msg.success(`任务 #${taskId} 已删除`);
      loadTasks();
    } catch {
      msg.error("删除失败");
    }
  };

  const handleUpdateTime = async (taskId: number) => {
    if (!editTime) return;
    try {
      const res = await fetch(`/api/tasks/${taskId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheduled_time: editTime.toISOString() }),
      });
      if (!res.ok) { const d = await res.json(); msg.error(d.detail || "修改失败"); return; }
      setEditingTaskId(null); setEditTime(null);
      msg.success("发送时间已更新");
      loadTasks();
    } catch { msg.error("修改失败"); }
  };

  const taskColumns: ColumnsType<TaskItem> = [
    { title: "ID", dataIndex: "id", width: 70, render: (v) => <Text code style={{ whiteSpace: "nowrap" }}>#{v}</Text> },
    {
      title: "分组", width: 140,
      render: (_, t) => (t.task_config as { group_key?: string })?.group_key ?? <Text type="secondary">—</Text>,
    },
    {
      title: "计划发送时间", width: 200,
      render: (_, t) =>
        editingTaskId === t.id ? (
          <Space>
            <DatePicker
              showTime
              value={editTime}
              onChange={setEditTime}
              format="YYYY-MM-DD HH:mm"
              size="small"
            />
            <Button size="small" type="primary" onClick={() => handleUpdateTime(t.id)}>保存</Button>
            <Button size="small" onClick={() => { setEditingTaskId(null); setEditTime(null); }}>取消</Button>
          </Space>
        ) : (
          <Text style={{ fontSize: 12 }}>{new Date(t.scheduled_time).toLocaleString("zh-CN")}</Text>
        ),
    },
    {
      title: "状态", width: 100,
      render: (_, t) => {
        const s = TASK_STATUS[t.status] ?? { color: "default", label: t.status };
        return (
          <>
            <Badge status={s.color as Parameters<typeof Badge>[0]["status"]} text={s.label} />
            {t.status === "failed" && t.failure_reason && (
              <div><Text type="danger" style={{ fontSize: 11 }}>{t.failure_reason}</Text></div>
            )}
          </>
        );
      },
    },
    {
      title: "操作", width: 220,
      render: (_, t) => (
        <Space>
          {t.status === "pending" && editingTaskId !== t.id && (
            <>
              <Button size="small" icon={<ThunderboltOutlined />} onClick={() => handleExecuteNow(t.id)}>
                立即发送
              </Button>
              <Button size="small" onClick={() => { setEditingTaskId(t.id); setEditTime(dayjs(t.scheduled_time)); }}>
                改时间
              </Button>
            </>
          )}
          <Popconfirm
            title="确认删除此任务？"
            onConfirm={() => handleDeleteTask(t.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const recipientCols: ColumnsType<RecipientItem> = [
    { title: "姓名", dataIndex: "name", width: 90 },
    { title: "邮箱", dataIndex: "email", width: 200, render: (v) => <Text code style={{ fontSize: 11 }}>{v}</Text> },
    {
      title: "操作", width: 80,
      render: (_, r) => (
        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteRecipient(r.id)}>
          移除
        </Button>
      ),
    },
  ];

  return (
    <Spin spinning={loading}>
      {msgCtx}


      <Title level={4} style={{ marginBottom: 24 }}>{taskTypeName} — 任务配置</Title>

      <Row gutter={[16, 16]}>
        {/* ── 左列 ── */}
        <Col xs={24} lg={10}>

          {/* 收件人配置 */}
          <Card title="收件人配置" style={{ marginBottom: 16 }}>
            {contacts.length === 0 ? (
              <Alert message="通讯录为空，请先在通讯录页面添加联系人" type="warning" showIcon />
            ) : (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Select
                  mode="multiple"
                  placeholder="选择联系人（可多选）"
                  value={selectedContactIds}
                  onChange={setSelectedContactIds}
                  style={{ width: "100%" }}
                  optionFilterProp="label"
                  options={available.map((c) => ({
                    value: c.id,
                    label: `${c.name}（${c.email}）${c.location ? ` [${c.location}]` : ""}`,
                  }))}
                />
                <div style={{ display: "flex", gap: 8 }}>
                  <Select
                    value={selectedRole}
                    onChange={setSelectedRole}
                    style={{ width: 160 }}
                    options={[
                      { value: "to", label: "收件人（TO）" },
                      { value: "cc", label: "抄送人（CC）" },
                    ]}
                  />
                  <Button type="primary" icon={<PlusOutlined />} onClick={handleAddRecipient}>
                    添加
                  </Button>
                </div>
              </Space>
            )}

            {(toRecipients.length > 0 || ccRecipients.length > 0) && (
              <Divider style={{ margin: "16px 0" }} />
            )}

            {toRecipients.length > 0 && (
              <>
                <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
                  TO 收件人（{toRecipients.length} 人）
                </Text>
                <Table
                  columns={recipientCols}
                  dataSource={toRecipients}
                  rowKey="id"
                  size="small"
                  pagination={false}
                  style={{ marginBottom: 12 }}
                />
              </>
            )}
            {ccRecipients.length > 0 && (
              <>
                <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
                  CC 抄送人（每封都抄送）
                </Text>
                <Table
                  columns={recipientCols}
                  dataSource={ccRecipients}
                  rowKey="id"
                  size="small"
                  pagination={false}
                />
              </>
            )}
          </Card>

          {/* 分组设置：仅内置任务显示 */}
          {isBuiltinTask && (
            <Card title="分组设置" style={{ marginBottom: 16 }}>
              <Space direction="vertical" style={{ width: "100%" }}>
                {isIpStatsTask ? (
                  <div>
                    <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 6 }}>发送地区</Text>
                    <Select
                      value={ipLocation}
                      onChange={setIpLocation}
                      style={{ width: "100%" }}
                      options={[
                        { value: "药源", label: "药源" },
                        { value: "重庆", label: "重庆" },
                      ]}
                    />
                  </div>
                ) : (
                  <>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 6 }}>分组维度</Text>
                      <Select
                        value={groupBy}
                        onChange={(v) => setGroupBy(v)}
                        style={{ width: "100%" }}
                        options={[
                          { value: "location", label: "按区域" },
                          { value: "department", label: "按部门" },
                          { value: "business_unit", label: "按事业部" },
                        ]}
                      />
                    </div>
                    {toRecipients.length > 0 && groupKeys.length === 0 && (
                      <Alert
                        message={`部分收件人的"${GROUP_LABELS[groupBy]}"字段为空，请在通讯录中补充`}
                        type="warning" showIcon
                      />
                    )}
                  </>
                )}
                {groupKeys.length > 0 && (
                  <div>
                    {groupKeys.map((key) => (
                      <div key={key} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "6px 10px", marginBottom: 4,
                        background: "#f6f8ff", borderRadius: 6, border: "1px solid #e6eaff",
                      }}>
                        <Text strong style={{ fontSize: 13 }}>{key}</Text>
                        <Tag color="blue">{groups[key].length} 人</Tag>
                      </div>
                    ))}
                  </div>
                )}
              </Space>
            </Card>
          )}

          {/* 附件 */}
          <Card title="附件文件">
            <Upload
              beforeUpload={(file) => {
                setFileList((prev) => [...prev, { file, name: file.name }]);
                return false;
              }}
              onRemove={(f) => setFileList((prev) => prev.filter((x) => x.name !== f.name))}
              fileList={fileList.map((f) => ({ uid: f.name, name: f.name, status: "done" }))}
            >
              <Button icon={<UploadOutlined />}>选择附件</Button>
            </Upload>
            <Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: 8 }}>
              所有分组邮件共用相同附件
            </Text>
          </Card>
        </Col>

        {/* ── 右列 ── */}
        <Col xs={24} lg={14}>

          {/* 发件人选择 */}
          {credentials.length > 0 && (
            <Card title="发件人" style={{ marginBottom: 16 }}>
              <Select
                value={selectedCredentialId}
                onChange={setSelectedCredentialId}
                style={{ width: "100%" }}
                options={credentials.map(c => ({ value: c.id, label: c.email }))}
                placeholder="选择发件邮箱"
              />
              {credentials.length === 0 && (
                <Text type="secondary" style={{ fontSize: 12 }}>请先在「系统设置」添加 SMTP 凭据</Text>
              )}
            </Card>
          )}

          {/* 发送时间 */}
          <Card title="发送时间" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: "100%" }}>
              {scheduledTimes.map((t, idx) => (
                <div key={idx} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <Text type="secondary" style={{ fontSize: 12, minWidth: 24 }}>#{idx + 1}</Text>
                  <DatePicker
                    showTime
                    value={t}
                    onChange={(v) => { const next = [...scheduledTimes]; next[idx] = v; setScheduledTimes(next); }}
                    format="YYYY-MM-DD HH:mm"
                    style={{ flex: 1 }}
                    placeholder="选择发送时间"
                  />
                  {scheduledTimes.length > 1 && (
                    <Button
                      size="small" danger
                      onClick={() => setScheduledTimes(scheduledTimes.filter((_, i) => i !== idx))}
                    >
                      删除
                    </Button>
                  )}
                </div>
              ))}
              <Button
                size="small"
                icon={<PlusOutlined />}
                onClick={() => setScheduledTimes([...scheduledTimes, null])}
              >
                添加时间点
              </Button>
              {scheduledTimes.some(Boolean) && groupKeys.length > 0 && (
                <Alert
                  message={`将创建 ${scheduledTimes.filter(Boolean).length} × ${groupKeys.length} = ${scheduledTimes.filter(Boolean).length * groupKeys.length} 个定时任务`}
                  type="info"
                />
              )}
            </Space>
          </Card>

          {/* 操作按钮 */}
          <Card style={{ marginBottom: 16 }}>
            <Space>
              <Button icon={<EyeOutlined />} onClick={handlePreview}>预览邮件</Button>
              <Button
                type="primary"
                icon={<SendOutlined />}
                loading={creating}
                onClick={handleCreateTask}
              >
                创建定时任务
              </Button>
            </Space>
          </Card>

          {/* 邮件预览 */}
          {preview && preview.emails.length > 0 && (
            <Card title={`邮件预览（共 ${preview.emails.length} 封）`} style={{ marginBottom: 16 }}>
              <Collapse
                size="small"
                items={preview.emails.map((em, idx) => ({
                  key: idx,
                  label: (
                    <Space>
                      <Tag color="blue">{em.group_key}</Tag>
                      <Text style={{ fontSize: 12 }} type="secondary">{em.subject}</Text>
                    </Space>
                  ),
                  children: (
                    <>
                      <Descriptions size="small" column={1} style={{ marginBottom: 12 }}>
                        <Descriptions.Item label="TO">
                          {em.to_recipients.map((r) => `${r.name} <${r.email}>`).join(", ")}
                        </Descriptions.Item>
                        {em.cc_recipients.length > 0 && (
                          <Descriptions.Item label="CC">
                            {em.cc_recipients.map((r) => `${r.name} <${r.email}>`).join(", ")}
                          </Descriptions.Item>
                        )}
                        <Descriptions.Item label="主题">{em.subject}</Descriptions.Item>
                      </Descriptions>
                      <div
                        style={{ background: "#fafafa", border: "1px solid #f0f0f0", borderRadius: 6, padding: 16, fontSize: 13, lineHeight: 1.8 }}
                        dangerouslySetInnerHTML={{ __html: em.body_html }}
                      />
                    </>
                  ),
                }))}
              />
            </Card>
          )}

          {/* 任务历史 */}
          {tasks.length > 0 && (
            <Card title="已创建的任务">
              <Table
                columns={taskColumns}
                dataSource={tasks}
                rowKey="id"
                size="small"
                pagination={false}
                scroll={{ x: 600 }}
              />
            </Card>
          )}
        </Col>
      </Row>
    </Spin>
  );
}

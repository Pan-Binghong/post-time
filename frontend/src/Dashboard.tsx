import { useCallback, useEffect, useRef, useState } from "react";
import {
  Button, Card, Col, Progress, Row, Space, Spin, Table, Tag, Typography, message,
} from "antd";
import {
  ReloadOutlined, DownloadOutlined, SettingOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { fetchDashboardOverview, fetchTaskTypeDetail, fetchExportReport, fetchTasks, checkTaskReplies } from "./api";
import type { TaskTypeSummary, TaskTypeDetail, RecipientStatus, ReplyCheckResponse } from "./types";

const { Title, Text } = Typography;
const AUTO_REFRESH = 30_000;

function statusTag(status: string) {
  const map: Record<string, { color: string; label: string }> = {
    replied:           { color: "success", label: "已回复"   },
    not_replied:       { color: "warning", label: "未回复"   },
    pending_follow_up: { color: "error",   label: "待跟进"   },
    sent:              { color: "processing", label: "已发送" },
    failed:            { color: "error",   label: "发送失败" },
  };
  const s = map[status] ?? { color: "default", label: status };
  return <Tag color={s.color}>{s.label}</Tag>;
}

const detailColumns: ColumnsType<RecipientStatus> = [
  { title: "姓名", dataIndex: "name", width: 100 },
  { title: "邮箱", dataIndex: "email", width: 200, render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text> },
  { title: "发送状态", dataIndex: "send_status",  width: 110, render: (v) => v ? statusTag(v) : <Text type="secondary">—</Text> },
  { title: "回复状态", dataIndex: "reply_status", width: 110, render: (v) => v ? statusTag(v) : <Text type="secondary">—</Text> },
  {
    title: "回复时间", dataIndex: "reply_timestamp", width: 180,
    render: (v) => v ? <Text style={{ fontSize: 12 }}>{new Date(v).toLocaleString("zh-CN")}</Text> : <Text type="secondary">—</Text>,
  },
];

function TaskTypeDetailView({ taskTypeId }: { taskTypeId: number }) {
  const [detail, setDetail] = useState<TaskTypeDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDetail = useCallback(() => {
    setLoading(true);
    fetchTaskTypeDetail(taskTypeId).then(setDetail).finally(() => setLoading(false));
  }, [taskTypeId]);

  useEffect(() => { loadDetail(); }, [loadDetail]);
  useEffect(() => {
    const t = setInterval(() => fetchTaskTypeDetail(taskTypeId).then(setDetail).catch(() => {}), AUTO_REFRESH);
    return () => clearInterval(t);
  }, [taskTypeId]);

  return (
    <Spin spinning={loading}>
      {detail && (
        <>
          <Title level={4} style={{ marginBottom: 4 }}>{detail.name}</Title>
          {detail.description && <Text type="secondary" style={{ display: "block", marginBottom: 16 }}>{detail.description}</Text>}
          <Table
            columns={detailColumns}
            dataSource={detail.recipients}
            rowKey="recipient_id"
            size="small"
            pagination={false}
            bordered={false}
          />
        </>
      )}
    </Spin>
  );
}

export default function Dashboard({
  onConfigureTask,
}: {
  onConfigureTask?: (id: number, name: string) => void;
}) {
  const [taskTypes, setTaskTypes] = useState<TaskTypeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [msg, msgCtx] = message.useMessage();

  const load = useCallback(() => {
    setLoading(true);
    fetchDashboardOverview()
      .then((d) => setTaskTypes(d.task_types))
      .catch(() => msg.error("加载失败"))
      .finally(() => setLoading(false));
  }, [msg]);

  const handleRefresh = useCallback(async () => {
    setChecking(true);
    try {
      const tasks = await fetchTasks();
      const completedIds = tasks.filter(t => t.status === "completed").map(t => t.id);
      if (completedIds.length === 0) {
        msg.info("暂无已完成的任务需要检查");
        setChecking(false);
        load();
        return;
      }
      const results = await Promise.allSettled(completedIds.map(id => checkTaskReplies(id)));
      const matched = results
        .filter(r => r.status === "fulfilled")
        .reduce((sum, r) => sum + (r as PromiseFulfilledResult<ReplyCheckResponse>).value.newly_matched_count, 0);
      msg.success(`检查完成，共发现 ${matched} 条新回复`);
    } catch {
      msg.error("检查回复时发生错误");
    } finally {
      setChecking(false);
    }
    load();
  }, [load, msg]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (selectedId !== null) { if (intervalRef.current) clearInterval(intervalRef.current); return; }
    intervalRef.current = setInterval(() => fetchDashboardOverview().then((d) => setTaskTypes(d.task_types)).catch(() => {}), AUTO_REFRESH);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [selectedId]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const report = await fetchExportReport();
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), {
        href: url, download: `email-export-${report.exported_at.replace(/[:.]/g, "-")}.json`,
      });
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
      msg.success("导出成功");
    } catch { msg.error("导出失败"); }
    finally { setExporting(false); }
  };

  if (selectedId !== null) {
    return <TaskTypeDetailView taskTypeId={selectedId} />;
  }

  return (
    <>
      {msgCtx}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0 }}>邮件看板</Title>
        <Space>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={handleExport}>导出报告</Button>
          <Button icon={<ReloadOutlined />} loading={checking} onClick={handleRefresh}>检查回复并刷新</Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          {taskTypes.map((tt) => {
            const pct = tt.total_recipients > 0
              ? Math.round((tt.replied_count / tt.total_recipients) * 100)
              : 0;
            return (
              <Col xs={24} sm={24} md={12} lg={8} key={tt.task_type_id}>
                <Card
                  hoverable
                  style={{ cursor: "pointer" }}
                  styles={{ body: { padding: "20px" } }}
                  onClick={() => setSelectedId(tt.task_type_id)}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
                    <Text strong style={{ fontSize: 15 }}>{tt.name}</Text>
                    <Button
                      size="small"
                      type="primary"
                      icon={<SettingOutlined />}
                      onClick={(e) => { e.stopPropagation(); onConfigureTask?.(tt.task_type_id, tt.name); }}
                    >
                      配置
                    </Button>
                  </div>
                  {tt.description && (
                    <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
                      {tt.description}
                    </Text>
                  )}
                  <Progress percent={pct} size="small" style={{ marginBottom: 12 }} />
                  <Row gutter={16}>
                    <Col span={8} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 22, fontWeight: 700, color: "#1a1a1a" }}>{tt.total_recipients}</div>
                      <Text type="secondary" style={{ fontSize: 11 }}>总计</Text>
                    </Col>
                    <Col span={8} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 22, fontWeight: 700, color: "#52c41a" }}>{tt.replied_count}</div>
                      <Text type="secondary" style={{ fontSize: 11 }}>已回复</Text>
                    </Col>
                    <Col span={8} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 22, fontWeight: 700, color: "#faad14" }}>{tt.not_replied_count}</div>
                      <Text type="secondary" style={{ fontSize: 11 }}>未回复</Text>
                    </Col>
                  </Row>
                </Card>
              </Col>
            );
          })}
        </Row>
        {!loading && taskTypes.length === 0 && (
          <Card style={{ textAlign: "center", padding: 40 }}>
            <Text type="secondary">暂无任务类型数据</Text>
          </Card>
        )}
      </Spin>
    </>
  );
}

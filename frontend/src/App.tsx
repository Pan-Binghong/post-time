import { useState } from "react";
import { ConfigProvider, Layout, Menu, theme } from "antd";
import {
  DashboardOutlined,
  ContactsOutlined,
  SettingOutlined,
  MailOutlined,
  AppstoreAddOutlined,
} from "@ant-design/icons";
import zhCN from "antd/locale/zh_CN";
import Dashboard from "./Dashboard";
import Settings from "./Settings";
import Contacts from "./Contacts";
import TaskConfig from "./TaskConfig";
import CustomTaskTypes from "./CustomTaskTypes";
import "./App.css";

const { Header, Content } = Layout;

type Page =
  | { type: "dashboard" }
  | { type: "settings" }
  | { type: "contacts" }
  | { type: "customTasks" }
  | { type: "taskConfig"; taskTypeId: number; taskTypeName: string };

export default function App() {
  const [page, setPage] = useState<Page>({ type: "dashboard" });

  const activeKey = page.type === "taskConfig" ? "dashboard" : page.type === "customTasks" ? "customTasks" : page.type;

  return (
    <ConfigProvider locale={zhCN} theme={{ algorithm: theme.defaultAlgorithm }}>
      <Layout style={{ minHeight: "100vh", background: "#f5f5f5" }}>
        <Header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            padding: "0 24px",
            background: "#fff",
            borderBottom: "1px solid #f0f0f0",
            boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginRight: 40, flexShrink: 0 }}>
            <div
              style={{
                width: 32, height: 32, borderRadius: 8,
                background: "linear-gradient(135deg, #1677ff 0%, #0958d9 100%)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              <MailOutlined style={{ color: "#fff", fontSize: 16 }} />
            </div>
            <span style={{ fontSize: 16, fontWeight: 600, color: "#1a1a1a", whiteSpace: "nowrap" }}>
              邮件追踪系统
            </span>
          </div>

          <Menu
            mode="horizontal"
            selectedKeys={[activeKey]}
            style={{ flex: 1, border: "none", lineHeight: "64px" }}
            items={[
              { key: "dashboard",   icon: <DashboardOutlined />,    label: "看板" },
              { key: "contacts",    icon: <ContactsOutlined />,     label: "通讯录" },
              { key: "customTasks", icon: <AppstoreAddOutlined />,  label: "自定义任务" },
              { key: "settings",    icon: <SettingOutlined />,      label: "系统设置" },
            ]}
            onClick={({ key }) => setPage({ type: key as "dashboard" | "contacts" | "customTasks" | "settings" })}
          />
        </Header>

        <Content style={{ padding: "24px", maxWidth: 1600, margin: "0 auto", width: "100%" }}>
          {page.type === "dashboard" && (
            <Dashboard
              onConfigureTask={(id, name) =>
                setPage({ type: "taskConfig", taskTypeId: id, taskTypeName: name })
              }
            />
          )}
          {page.type === "settings" && <Settings />}
          {page.type === "contacts" && <Contacts />}
          {page.type === "customTasks" && (
            <CustomTaskTypes
              onConfigureTask={(id, name) =>
                setPage({ type: "taskConfig", taskTypeId: id, taskTypeName: name })
              }
            />
          )}
          {page.type === "taskConfig" && (
            <TaskConfig
              taskTypeId={page.taskTypeId}
              taskTypeName={page.taskTypeName}
              onBack={() => setPage({ type: "dashboard" })}
            />
          )}
        </Content>
      </Layout>
    </ConfigProvider>
  );
}

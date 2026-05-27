import axios from "axios";
import type {
  CredentialResponse, CredentialItem, DashboardOverview, TaskTypeDetail, StatsResponse,
  ExportReport, ContactItem, RecipientItem, TaskItem, PreviewResponse,
  TaskTypeItem, TemplateItem,
} from "./types";

const client = axios.create({ baseURL: "/api" });

// 请求拦截：自动携带 Bearer token
client.interceptors.request.use(config => {
  const token = localStorage.getItem("auth_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 响应拦截：401 自动清除 token 并刷新页面到登录
client.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem("auth_token");
      window.location.reload();
    }
    return Promise.reject(err);
  }
);

// Auth
export const login = (username: string, password: string) =>
  axios.post<{ access_token: string; token_type: string }>("/api/auth/login", { username, password })
    .then(r => r.data);

// Credentials
export const fetchCredentialList = () =>
  client.get<CredentialItem[]>("/credentials/list").then(r => r.data);
export const saveCredentials = (email: string, smtpCode: string) =>
  client.post<CredentialItem>("/credentials", { email, smtp_code: smtpCode }).then(r => r.data);
export const deleteCredential = (id: number) =>
  client.delete(`/credentials/${id}`);
export const fetchCredentials = () =>
  client.get<CredentialResponse | null>("/credentials").then(r => r.data);

// Dashboard
export const fetchDashboardOverview = () =>
  client.get<DashboardOverview>("/dashboard").then(r => r.data);
export const fetchTaskTypeDetail = (id: number) =>
  client.get<TaskTypeDetail>(`/dashboard/${id}`).then(r => r.data);
export const fetchTaskTypeStats = (id: number) =>
  client.get<StatsResponse>(`/dashboard/${id}/stats`).then(r => r.data);
export const fetchExportReport = () =>
  client.get<ExportReport>("/dashboard/export").then(r => r.data);

// Contacts
export const fetchContacts = () =>
  client.get<ContactItem[]>("/contacts").then(r => r.data);
export const createContact = (c: Omit<ContactItem, "id">) =>
  client.post<ContactItem>("/contacts", c).then(r => r.data);
export const updateContact = (id: number, c: Partial<ContactItem>) =>
  client.put<ContactItem>(`/contacts/${id}`, c).then(r => r.data);
export const deleteContact = (id: number) =>
  client.delete(`/contacts/${id}`);

// Recipients
export const fetchRecipients = (taskTypeId: number) =>
  client.get<RecipientItem[]>(`/recipients/${taskTypeId}`).then(r => r.data);
export const addRecipient = (taskTypeId: number, contactId: number, role: string) =>
  client.post<RecipientItem>(`/recipients/${taskTypeId}`, { contact_id: contactId, role }).then(r => r.data);
export const deleteRecipient = (taskTypeId: number, recipientId: number) =>
  client.delete(`/recipients/${taskTypeId}/${recipientId}`);

// Tasks
export const fetchTasks = () =>
  client.get<TaskItem[]>("/tasks").then(r => r.data);
export const createTask = (fd: FormData) =>
  client.post<TaskItem[]>("/tasks", fd, { headers: { "Content-Type": "multipart/form-data" } }).then(r => r.data);
export const executeTask = (taskId: number) =>
  client.post(`/tasks/${taskId}/execute`).then(r => r.data);
export const deleteTask = (taskId: number) =>
  client.delete(`/tasks/${taskId}`);

// Task Types CRUD
export const fetchTaskTypes = () =>
  client.get<TaskTypeItem[]>("/task-types").then(r => r.data);
export const createTaskType = (data: { name: string; description: string; template_id: number | null }) =>
  client.post<TaskTypeItem>("/task-types", data).then(r => r.data);
export const updateTaskType = (id: number, data: Partial<{ name: string; description: string; template_id: number | null }>) =>
  client.put<TaskTypeItem>(`/task-types/${id}`, data).then(r => r.data);
export const deleteTaskType = (id: number) =>
  client.delete(`/task-types/${id}`);

// Templates CRUD
export const fetchTemplates = () =>
  client.get<TemplateItem[]>("/templates").then(r => r.data);
export const createTemplate = (data: { name: string; subject: string; body: string }) =>
  client.post<TemplateItem>("/templates", data).then(r => r.data);
export const updateTemplate = (id: number, data: Partial<{ name: string; subject: string; body: string }>) =>
  client.put<TemplateItem>(`/templates/${id}`, data).then(r => r.data);
export const deleteTemplate = (id: number) =>
  client.delete(`/templates/${id}`);

// Reply check
export const checkTaskReplies = (taskId: number) =>
  client.post(`/tasks/${taskId}/check-replies`).then(r => r.data);

// Preview
export const previewPatentEmail = (params: {
  task_type_id: number;
  group_by?: string;
  scheduled_time?: string;
  attachment_names?: string[];
}) => client.post<PreviewResponse>("/preview/patent", params).then(r => r.data);

export interface CredentialResponse {
  email: string;
  smtp_code_masked: string;
  message: string;
}

export interface CredentialItem {
  id: number;
  email: string;
  smtp_code_masked: string;
}

export interface RecipientStatus {
  recipient_id: number;
  name: string;
  email: string;
  send_status: string | null;
  reply_status: string | null;
  reply_timestamp: string | null;
}

export interface TaskTypeSummary {
  task_type_id: number;
  name: string;
  description: string;
  total_recipients: number;
  replied_count: number;
  not_replied_count: number;
}

export interface TaskTypeDetail {
  task_type_id: number;
  name: string;
  description: string;
  recipients: RecipientStatus[];
}

export interface DashboardOverview { task_types: TaskTypeSummary[]; }
export interface ExportReport { exported_at: string; task_types: TaskTypeDetail[]; }
export interface StatsResponse {
  task_type_id: number; name: string;
  total_recipients: number; replied_count: number; not_replied_count: number;
}

export interface TaskTypeItem {
  id: number;
  name: string;
  description: string;
  template_id: number | null;
}

export interface TemplateItem {
  id: number;
  name: string;
  subject: string;
  body: string;
}

export interface ContactItem {
  id: number;
  name: string;
  email: string;
  department: string;
  business_unit: string;
  location: string;
}

export interface RecipientItem {
  id: number;
  task_type_id: number;
  contact_id: number;
  role: string;
  name: string;
  email: string;
  department: string;
  business_unit: string;
  location: string;
}

export interface TaskItem {
  id: number;
  task_type_id: number;
  template_id: number | null;
  credential_id: number | null;
  scheduled_time: string;
  status: string;
  failure_reason: string | null;
  task_config: Record<string, string | number> | null;
  attachments: string[] | null;
}

export interface PreviewRecipient {
  name: string; email: string; role: string;
}

export interface LocationEmail {
  group_key: string;
  subject: string;
  body_html: string;
  to_recipients: PreviewRecipient[];
  cc_recipients: PreviewRecipient[];
}

export interface PreviewResponse {
  emails: LocationEmail[];
}

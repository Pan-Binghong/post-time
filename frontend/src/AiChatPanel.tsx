import { useRef, useState } from "react";
import {
  Alert, Button, Input, Space, Spin, Tag, Tooltip, Typography,
} from "antd";
import { RobotOutlined, SendOutlined, CheckOutlined, ClearOutlined } from "@ant-design/icons";

const { TextArea } = Input;
const { Text } = Typography;

interface AiResult {
  subject: string;
  body: string;
}

interface Props {
  onApply: (result: AiResult) => void;
}

const SUGGESTIONS = [
  "按季度收集各部门工作数据，截止日发件后10个工作日",
  "季度文档收集，附件为空白表，10个工作日截止",
  "通知各部门更新Q{{quarter}}季度统计表",
];

export default function AiChatPanel({ onApply }: Props) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [lastResult, setLastResult] = useState<AiResult | null>(null);
  const [parseError, setParseError] = useState("");
  const abortRef = useRef<(() => void) | null>(null);

  const send = async (text?: string) => {
    const userMsg = text ?? input.trim();
    if (!userMsg || streaming) return;
    setInput("");
    setParseError("");
    setLastResult(null);

    const newMessages = [...messages, { role: "user", content: userMsg }];
    setMessages(newMessages);

    setStreaming(true);
    let accumulated = "";
    let assistantAdded = false;

    try {
      const resp = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: newMessages, stream: true }),
      });

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let aborted = false;
      abortRef.current = () => { aborted = true; reader.cancel(); };

      while (true) {
        const { done, value } = await reader.read();
        if (done || aborted) break;
        const text = decoder.decode(value);
        for (const line of text.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();
          if (data === "[DONE]") break;
          try {
            const chunk = JSON.parse(data);
            if (chunk.error) { setParseError("AI 服务出错：" + chunk.error); break; }
            accumulated += chunk.content ?? "";
            if (!assistantAdded) {
              setMessages(prev => [...prev, { role: "assistant", content: accumulated }]);
              assistantAdded = true;
            } else {
              setMessages(prev => {
                const next = [...prev];
                next[next.length - 1] = { role: "assistant", content: accumulated };
                return next;
              });
            }
          } catch { /* skip malformed */ }
        }
      }

      // 尝试解析 JSON 结果
      try {
        // 去掉可能的 markdown 代码块
        const clean = accumulated.replace(/^```(?:json)?\n?/m, "").replace(/\n?```$/m, "").trim();
        // 提取 <think>...</think> 之后的内容（qwen3 有思考过程）
        const withoutThink = clean.replace(/<think>[\s\S]*?<\/think>/g, "").trim();
        const result: AiResult = JSON.parse(withoutThink);
        if (result.subject && result.body) {
          setLastResult(result);
        } else {
          setParseError("AI 返回格式不正确，请重试");
        }
      } catch {
        setParseError("无法解析 AI 返回结果，请重新描述需求");
      }
    } catch (e) {
      setParseError("请求失败：" + String(e));
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const clear = () => {
    setMessages([]);
    setLastResult(null);
    setParseError("");
    setInput("");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 8 }}>
      {/* 标题 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, paddingBottom: 4, borderBottom: "1px solid #f0f0f0" }}>
        <RobotOutlined style={{ color: "#1677ff", fontSize: 16 }} />
        <Text strong style={{ fontSize: 13 }}>AI 邮件助手</Text>
        <Tooltip title="清空对话">
          <Button size="small" type="text" icon={<ClearOutlined />} onClick={clear} />
        </Tooltip>
      </div>

      {/* 快捷建议 */}
      {messages.length === 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {SUGGESTIONS.map((s, i) => (
            <Tag
              key={i}
              style={{ cursor: "pointer", fontSize: 11, padding: "2px 8px" }}
              color="blue"
              onClick={() => send(s)}
            >
              {s}
            </Tag>
          ))}
        </div>
      )}

      {/* 对话历史 */}
      <div style={{
        flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8,
        minHeight: 120, maxHeight: 320, padding: "4px 0",
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === "user" ? "flex-end" : "flex-start",
            maxWidth: "90%",
          }}>
            <div style={{
              background: m.role === "user" ? "#1677ff" : "#f5f5f5",
              color: m.role === "user" ? "#fff" : "#333",
              borderRadius: m.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
              padding: "6px 10px",
              fontSize: 12,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}>
              {/* 隐藏 <think> 内容，只展示结果 */}
              {m.role === "assistant"
                ? m.content.replace(/<think>[\s\S]*?<\/think>/g, "").trim() || "思考中…"
                : m.content}
            </div>
          </div>
        ))}
        {streaming && messages[messages.length - 1]?.role !== "assistant" && (
          <div style={{ alignSelf: "flex-start" }}>
            <Spin size="small" />
          </div>
        )}
      </div>

      {/* 解析错误 */}
      {parseError && <Alert message={parseError} type="warning" showIcon style={{ fontSize: 11 }} />}

      {/* 应用按钮 */}
      {lastResult && (
        <Button
          type="primary"
          icon={<CheckOutlined />}
          size="small"
          onClick={() => onApply(lastResult)}
          style={{ alignSelf: "stretch" }}
        >
          应用到模板（主题 + 正文）
        </Button>
      )}

      {/* 输入框 */}
      <Space.Compact style={{ width: "100%" }}>
        <TextArea
          value={input}
          onChange={e => setInput(e.target.value)}
          onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder={"描述需求，回车发送\nShift+Enter 换行"}
          autoSize={{ minRows: 2, maxRows: 4 }}
          style={{ fontSize: 12, resize: "none" }}
          disabled={streaming}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={() => send()}
          loading={streaming}
          style={{ height: "auto", alignSelf: "stretch" }}
        />
      </Space.Compact>
    </div>
  );
}

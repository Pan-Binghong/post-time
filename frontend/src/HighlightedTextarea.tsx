import { forwardRef, useCallback, useRef, useState } from "react";

// ── 占位符元数据（颜色方案）
export const PLACEHOLDER_META = [
  // 收件人
  { key: "name",       label: "{{name}}",       desc: "收件人姓名",           bg: "#ede9fe", fg: "#6d28d9" },
  { key: "location",   label: "{{location}}",   desc: "分组/地区",            bg: "#dbeafe", fg: "#1d4ed8" },
  // 年季度
  { key: "year",       label: "{{year}}",       desc: "年份",                 bg: "#dcfce7", fg: "#15803d" },
  { key: "quarter",    label: "{{quarter}}",    desc: "季度（1-4）",           bg: "#dcfce7", fg: "#15803d" },
  // 月份
  { key: "month",      label: "{{month}}",      desc: "月份数字（1-12）",      bg: "#d1fae5", fg: "#065f46" },
  { key: "month_cn",   label: "{{month_cn}}",   desc: "月份中文（一月…十二月）", bg: "#d1fae5", fg: "#065f46" },
  // 周
  { key: "week_num",   label: "{{week_num}}",   desc: "ISO 周次（1-53）",      bg: "#fce7f3", fg: "#9d174d" },
  { key: "week_start", label: "{{week_start}}", desc: "本周周一 YYYY.MM.DD",   bg: "#fce7f3", fg: "#9d174d" },
  { key: "week_end",   label: "{{week_end}}",   desc: "本周周日 YYYY.MM.DD",   bg: "#fce7f3", fg: "#9d174d" },
  // 日期
  { key: "date",       label: "{{date}}",       desc: "发送日 YYYY-MM-DD",     bg: "#fef9c3", fg: "#854d0e" },
  { key: "send_date",  label: "{{send_date}}",  desc: "发送日 YYYY.MM.DD",     bg: "#fef9c3", fg: "#854d0e" },
  { key: "deadline",   label: "{{deadline}}",   desc: "截止日（+10工作日）",    bg: "#fee2e2", fg: "#b91c1c" },
] as const;

const COLOR_MAP: Record<string, { bg: string; fg: string }> = Object.fromEntries(
  PLACEHOLDER_META.map(m => [m.key, { bg: m.bg, fg: m.fg }]),
);

function buildHighlight(text: string): string {
  // 1. 转义 HTML 特殊字符
  let s = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // 2. 将 HTML 标签变灰斜体（转义后形如 &lt;p&gt;）
  s = s.replace(
    /(&lt;(?:[^&]|&amp;|&quot;|&apos;)*?&gt;)/g,
    '<span style="color:#94a3b8;font-style:italic">$1</span>',
  );

  // 3. 高亮 {{占位符}}
  s = s.replace(/\{\{(\w+)\}\}/g, (_, key) => {
    const c = COLOR_MAP[key] ?? { bg: "#fde68a", fg: "#92400e" };
    return (
      `<mark style="background:${c.bg};color:${c.fg};` +
      `border-radius:3px;padding:0 3px;font-weight:700;font-style:normal;">{{${key}}}</mark>`
    );
  });

  // 4. 换行转 <br>，末尾加空格防止最后一行丢失
  return s.replace(/\n/g, "<br>") + "&nbsp;";
}

// 必须与 textarea 完全一致的排版属性
const TYPO: React.CSSProperties = {
  fontFamily: "'Courier New', Consolas, 'Lucida Console', monospace",
  fontSize: 13,
  lineHeight: "1.65",
  padding: "10px 12px",
  margin: 0,
  boxSizing: "border-box" as const,
  border: 0,
  outline: "none",
  overflowWrap: "break-word",
  wordBreak: "break-word",
  whiteSpace: "pre-wrap",
};

interface Props {
  value?: string;
  onChange?: (val: string) => void;
  placeholder?: string;
  minRows?: number;
}

const HighlightedTextarea = forwardRef<HTMLTextAreaElement, Props>(
  function HighlightedTextarea({ value = "", onChange, placeholder, minRows = 14 }, forwardedRef) {
    const bdRef = useRef<HTMLDivElement>(null);
    const innerRef = useRef<HTMLTextAreaElement>(null);
    const [focused, setFocused] = useState(false);

    // 合并 forwardedRef 与 innerRef
    const setRef = useCallback(
      (el: HTMLTextAreaElement | null) => {
        (innerRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
        if (typeof forwardedRef === "function") {
          forwardedRef(el);
        } else if (forwardedRef) {
          (forwardedRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
        }
      },
      [forwardedRef],
    );

    const syncScroll = () => {
      if (bdRef.current && innerRef.current) {
        bdRef.current.scrollTop = innerRef.current.scrollTop;
      }
    };

    const minH = minRows * 1.65 * 13 + 20;

    return (
      <div
        style={{
          position: "relative",
          borderRadius: 6,
          overflow: "hidden",
          border: `1px solid ${focused ? "#1677ff" : "#d9d9d9"}`,
          boxShadow: focused ? "0 0 0 2px rgba(22,119,255,0.1)" : undefined,
          background: "#f8fafc",
          transition: "border-color 0.2s, box-shadow 0.2s",
        }}
      >
        {/* 背景高亮层 */}
        <div
          ref={bdRef}
          aria-hidden
          style={{
            ...TYPO,
            position: "absolute",
            inset: 0,
            overflow: "hidden",
            pointerEvents: "none",
            color: "rgba(30,41,59,0.82)",
            background: "transparent",
            zIndex: 0,
            width: "100%",
          }}
          dangerouslySetInnerHTML={{ __html: buildHighlight(value) }}
        />
        {/* 透明输入层 */}
        <textarea
          ref={setRef}
          value={value}
          onChange={e => onChange?.(e.target.value)}
          onScroll={syncScroll}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          spellCheck={false}
          style={{
            ...TYPO,
            position: "relative",
            zIndex: 1,
            display: "block",
            width: "100%",
            minHeight: minH,
            resize: "vertical",
            color: "transparent",
            caretColor: "#1e293b",
            background: "transparent",
          }}
        />
      </div>
    );
  },
);

export default HighlightedTextarea;

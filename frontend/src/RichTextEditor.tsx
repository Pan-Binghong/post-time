import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

interface Props {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  minHeight?: number;
}

export interface RichTextEditorHandle {
  insertText: (text: string) => void;
  execCmd: (cmd: string, val?: string) => void;
  focus: () => void;
}

const RichTextEditor = forwardRef<RichTextEditorHandle, Props>(
  function RichTextEditor({ value, onChange, placeholder = "请输入正文…", minHeight = 380 }, ref) {
    const divRef = useRef<HTMLDivElement>(null);
    const skipSync = useRef(false);

    // 外部 value 变化时同步（AI 应用内容）
    // 清理标签间的换行/空白，防止 contentEditable 将其渲染为多余空行
    const clean = (html: string) => html.replace(/>\s*[\r\n]+\s*</g, '><').trim();

    useEffect(() => {
      const el = divRef.current;
      if (!el) return;
      const cleaned = clean(value);
      if (el.innerHTML !== cleaned) {
        skipSync.current = true;
        el.innerHTML = cleaned;
        skipSync.current = false;
      }
    }, [value]);

    useImperativeHandle(ref, () => ({
      insertText(text: string) {
        divRef.current?.focus();
        // 先开启 CSS 样式模式，再插入
        document.execCommand("styleWithCSS", false, "true");
        document.execCommand("insertText", false, text);
      },
      execCmd(cmd: string, val?: string) {
        divRef.current?.focus();
        document.execCommand("styleWithCSS", false, "true");
        document.execCommand(cmd, false, val);
        if (divRef.current) onChange(divRef.current.innerHTML);
      },
      focus() { divRef.current?.focus(); },
    }));

    const handleInput = () => {
      if (!skipSync.current && divRef.current) {
        onChange(divRef.current.innerHTML);
      }
    };

    return (
      <div style={{ position: "relative" }}>
        <div
          ref={divRef}
          contentEditable
          suppressContentEditableWarning
          onInput={handleInput}
          style={{
            minHeight,
            border: "1px solid #d9d9d9",
            borderRadius: 6,
            padding: "12px 14px",
            fontSize: 14,
            lineHeight: 1.8,
            outline: "none",
            fontFamily: "'Microsoft YaHei', 'PingFang SC', sans-serif",
            overflowY: "auto",
            background: "#fff",
            cursor: "text",
            transition: "border-color 0.2s",
          }}
          onFocus={e => (e.currentTarget.style.borderColor = "#1677ff")}
          onBlur={e => (e.currentTarget.style.borderColor = "#d9d9d9")}
        />
        {/* placeholder */}
        {!value && (
          <div
            style={{
              position: "absolute", top: 12, left: 14, pointerEvents: "none",
              color: "#bbb", fontSize: 14, lineHeight: 1.8,
            }}
          >
            {placeholder}
          </div>
        )}
      </div>
    );
  },
);

export default RichTextEditor;

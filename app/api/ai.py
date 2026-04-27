"""AI Chat API — 代理转发到 qwen3，支持流式 SSE 输出。"""

import json
import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["ai"])

AI_BASE_URL = "http://120.26.33.228:9997/v1"
AI_MODEL = "qwen3"
AI_API_KEY = "1"

SYSTEM_PROMPT = """\
你是一个专业的商务邮件助手。用户会描述他们想要的邮件内容，你的任务是生成一封完整的邮件。

输出格式必须严格遵守以下 JSON 格式（不要输出其他内容，不要有 markdown 代码块包裹）：
{
  "subject": "邮件主题",
  "body": "邮件正文 HTML"
}

可用占位符（原样保留在输出中，系统发送时自动替换）：
- {{name}}       收件人姓名
- {{location}}   分组/地区名称
- {{year}}       年份（如 2025）
- {{quarter}}    季度（1-4）
- {{month}}      月份数字（1-12）
- {{month_cn}}   月份中文（一、二…十二）
- {{week_num}}   ISO 周次（1-53）
- {{week_start}} 本周周一，格式 YYYY.MM.DD
- {{week_end}}   本周周日，格式 YYYY.MM.DD
- {{date}}       发送日，格式 YYYY-MM-DD
- {{send_date}}  发送日，格式 YYYY.MM.DD
- {{deadline}}   截止日（发送日+10工作日），格式 YYYY.MM.DD

正文要求：
- 使用 HTML 格式，段落用 <p> 包裹，换行用 <br>
- 可以使用 <b>加粗</b>、<span style="color:#e03030">红色</span>、<span style="color:#1a56db">蓝色</span> 等内联样式
- 保持专业商务风格，语气礼貌简洁
"""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    stream: bool = True


@router.post("/chat")
async def ai_chat(req: ChatRequest):
    """代理转发到 qwen3，流式返回 SSE 数据。"""
    payload = {
        "model": AI_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}]
                    + [{"role": m.role, "content": m.content} for m in req.messages],
        "stream": True,
    }

    async def event_stream():
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{AI_BASE_URL}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {AI_API_KEY}"},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data = line[6:]
                            if data.strip() == "[DONE]":
                                yield "data: [DONE]\n\n"
                                return
                            try:
                                chunk = json.loads(data)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    yield f"data: {json.dumps({'content': delta}, ensure_ascii=False)}\n\n"
                            except Exception:
                                pass
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

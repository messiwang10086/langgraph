from langchain.agents.middleware import before_agent, after_agent, before_model, after_model, AgentState
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig
from typing import Any
from datetime import datetime
import json


class AgentLogger:
    """统一的 Agent 状态记录器"""

    def __init__(self, log_file: str = "agent_logs.jsonl"):
        self.log_file = log_file

    def log(self, event_type: str, agent_name: str, data: dict):
        """记录日志到文件"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "agent_name": agent_name,
            **data
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# 全局日志记录器
logger = AgentLogger()


# ✅ 修正：同时接收 state、runtime 和 config
@before_agent
def log_agent_start(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig  # ✅ 添加 config 参数
) -> dict[str, Any] | None:
    """记录 Agent 开始执行"""
    # ✅ 从 config 获取 agent_name，不是 runtime.config
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    req_id = state.get("data", {}).get("req_id")
    creation_id = state.get("data", {}).get("creationId")

    logger.log(
        event_type="agent_start",  # ✅ 改为 agent_start 更清晰
        agent_name=agent_name,
        data={
            "req_id": req_id,
            "creation_id": creation_id
        }
    )
    return None


@after_agent
def log_agent_end(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig,  # ✅ 添加 config 参数
    result: Any = None  # ✅ 添加 result 参数接收模型输出
) -> dict[str, Any] | None:
    """记录 Agent 完成"""
    # ✅ 从 config 获取 agent_name
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    req_id = state.get("data", {}).get("req_id")
    creation_id = state.get("data", {}).get("creationId")

    # ✅ 从 state 获取 last_agent_output（如果 middleware 更新了 state）
    last_agent_output = state.get("last_agent_output")

    # 从 last_agent_output 中提取信息
    current_agent_summary = None
    current_agent_success = None
    current_agent_error = None
    model_output = None

    if last_agent_output is not None:
        if hasattr(last_agent_output, "summary"):
            current_agent_summary = last_agent_output.summary
            current_agent_success = getattr(last_agent_output, "success", None)
            current_agent_error = getattr(last_agent_output, "error", None)
        elif isinstance(last_agent_output, dict):
            current_agent_summary = last_agent_output.get("summary")
            current_agent_success = last_agent_output.get("success")
            current_agent_error = last_agent_output.get("error")

    # ✅ 如果 middleware 支持传入 result，优先使用 result
    if result is not None:
        if isinstance(result, dict):
            model_output = result.get("structured_response") or result
        else:
            model_output = str(result)

    logger.log(
        event_type="agent_end",
        agent_name=agent_name,
        data={
            "req_id": req_id,
            "creation_id": creation_id,
            "current_agent_summary": current_agent_summary,
            "current_agent_success": current_agent_success,
            "current_agent_error": current_agent_error,
            "model_output": model_output  # ✅ 记录模型输出
        }
    )
    return None


# ========== 如果您的 middleware 不支持 result 参数，使用这个版本 ==========
@after_agent
def log_agent_end_without_result(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig
) -> dict[str, Any] | None:
    """记录 Agent 完成（不依赖 result 参数的版本）"""
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    req_id = state.get("data", {}).get("req_id")
    creation_id = state.get("data", {}).get("creationId")

    # 从 state 中尝试获取所有可能的输出
    last_agent_output = state.get("last_agent_output")
    messages = state.get("messages", [])

    # 提取最后一条消息作为模型输出
    model_output = None
    if messages and len(messages) > 0:
        last_message = messages[-1]
        if isinstance(last_message, dict):
            model_output = last_message.get("content")
        elif hasattr(last_message, "content"):
            model_output = last_message.content

    current_agent_summary = None
    current_agent_success = None
    current_agent_error = None

    if last_agent_output is not None:
        if hasattr(last_agent_output, "summary"):
            current_agent_summary = last_agent_output.summary
            current_agent_success = getattr(last_agent_output, "success", None)
            current_agent_error = getattr(last_agent_output, "error", None)
        elif isinstance(last_agent_output, dict):
            current_agent_summary = last_agent_output.get("summary")
            current_agent_success = last_agent_output.get("success")
            current_agent_error = last_agent_output.get("error")

    logger.log(
        event_type="agent_end",
        agent_name=agent_name,
        data={
            "req_id": req_id,
            "creation_id": creation_id,
            "current_agent_summary": current_agent_summary,
            "current_agent_success": current_agent_success,
            "current_agent_error": current_agent_error,
            "model_output": model_output
        }
    )
    return None

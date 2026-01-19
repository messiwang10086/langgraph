"""
完整可运行的测试示例
展示如何正确使用 Runtime 和 Config
"""

from typing import TypedDict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

# ==================== 1. 定义数据结构 ====================

class AgentState(TypedDict):
    """Agent 状态"""
    data: dict
    messages: list
    last_agent_output: Optional[Any]


@dataclass
class AgentOutput:
    """Agent 输出结构"""
    summary: str
    success: bool
    error: Optional[str] = None


@dataclass
class Context:
    """Runtime Context"""
    user_id: str
    environment: str = "test"


# ==================== 2. 日志记录器 ====================

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
        print(f"[LOG] {json.dumps(log_entry, ensure_ascii=False)}")
        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


logger = AgentLogger()


# ==================== 3. Middleware 实现 ====================

def log_agent_start(
    state: AgentState,
    runtime: Runtime[Context],
    config: RunnableConfig
) -> None:
    """记录 Agent 开始执行"""
    # ✅ 从 config 获取 agent_name
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")

    # 从 state 获取业务信息
    req_id = state.get("data", {}).get("req_id")
    creation_id = state.get("data", {}).get("creationId")

    # 从 runtime 获取上下文信息
    user_id = runtime.context.user_id if runtime.context else "unknown"

    logger.log(
        event_type="agent_start",
        agent_name=agent_name,
        data={
            "req_id": req_id,
            "creation_id": creation_id,
            "thread_id": thread_id,
            "user_id": user_id
        }
    )


def log_agent_end(
    state: AgentState,
    runtime: Runtime[Context],
    config: RunnableConfig,
    result: Optional[Any] = None
) -> None:
    """记录 Agent 完成"""
    # ✅ 从 config 获取 agent_name
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")

    req_id = state.get("data", {}).get("req_id")
    creation_id = state.get("data", {}).get("creationId")

    # 从 runtime 获取上下文
    user_id = runtime.context.user_id if runtime.context else "unknown"

    # 提取模型输出
    model_output = None
    current_agent_summary = None
    current_agent_success = None
    current_agent_error = None

    # 方案 1: 从 result 参数获取
    if result is not None:
        if isinstance(result, dict):
            model_output = result.get("structured_response") or result
        elif isinstance(result, AgentOutput):
            current_agent_summary = result.summary
            current_agent_success = result.success
            current_agent_error = result.error
            model_output = {
                "summary": result.summary,
                "success": result.success,
                "error": result.error
            }
        else:
            model_output = str(result)

    # 方案 2: 从 state.last_agent_output 获取
    if model_output is None:
        last_agent_output = state.get("last_agent_output")
        if last_agent_output is not None:
            if hasattr(last_agent_output, "summary"):
                current_agent_summary = last_agent_output.summary
                current_agent_success = getattr(last_agent_output, "success", None)
                current_agent_error = getattr(last_agent_output, "error", None)
            elif isinstance(last_agent_output, dict):
                current_agent_summary = last_agent_output.get("summary")
                current_agent_success = last_agent_output.get("success")
                current_agent_error = last_agent_output.get("error")
            model_output = last_agent_output

    # 方案 3: 从 state.messages 获取最后一条消息
    if model_output is None:
        messages = state.get("messages", [])
        if messages and len(messages) > 0:
            last_message = messages[-1]
            if isinstance(last_message, dict):
                model_output = last_message.get("content")
            elif hasattr(last_message, "content"):
                model_output = last_message.content

    logger.log(
        event_type="agent_end",
        agent_name=agent_name,
        data={
            "req_id": req_id,
            "creation_id": creation_id,
            "thread_id": thread_id,
            "user_id": user_id,
            "current_agent_summary": current_agent_summary,
            "current_agent_success": current_agent_success,
            "current_agent_error": current_agent_error,
            "model_output": model_output
        }
    )


# ==================== 4. Agent 实现 ====================

def business_intent_agent(
    state: AgentState,
    *,
    runtime: Runtime[Context],
    config: RunnableConfig
) -> AgentOutput:
    """核心执行函数"""

    # 记录开始
    log_agent_start(state, runtime, config)

    # ✅ 使用 patch_configurable 合并配置
    try:
        from langgraph._internal._config import patch_configurable
        agent_config = patch_configurable(
            config,
            {"agent_name": "business_intent_agent"}
        )
    except ImportError:
        # 如果无法导入，手动合并
        agent_config = {
            **config,
            "configurable": {
                **config.get("configurable", {}),
                "agent_name": "business_intent_agent"
            }
        }

    # 模拟 agent 执行
    req_id = state["data"].get("req_id")
    creation_id = state["data"].get("creationId")

    print(f"\n[Agent] 开始处理:")
    print(f"  - req_id: {req_id}")
    print(f"  - creation_id: {creation_id}")
    print(f"  - agent_name: {agent_config['configurable']['agent_name']}")
    print(f"  - thread_id: {agent_config['configurable'].get('thread_id')}")
    print(f"  - user_id: {runtime.context.user_id if runtime.context else 'N/A'}")

    # 模拟处理
    result = AgentOutput(
        summary=f"成功处理请求 {req_id}",
        success=True,
        error=None
    )

    # 更新 state (实际使用中可能由框架自动处理)
    state["last_agent_output"] = result

    # 记录结束
    log_agent_end(state, runtime, agent_config, result)

    return result


# ==================== 5. 测试用例 ====================

def test_basic_usage():
    """测试基本用法"""
    print("\n" + "="*60)
    print("测试 1: 基本用法")
    print("="*60)

    # 构造 state
    state: AgentState = {
        "data": {
            "req_id": "test_req_001",
            "creationId": "test_creation_001"
        },
        "messages": [],
        "last_agent_output": None
    }

    # 构造 config
    config: RunnableConfig = {
        "configurable": {
            "thread_id": "test_thread_001"
        },
        "metadata": {
            "environment": "test",
            "version": "1.0.0"
        }
    }

    # 构造 runtime
    test_runtime = Runtime(
        context=Context(user_id="test_user_001", environment="test")
    )

    # 执行 agent
    result = business_intent_agent(state, runtime=test_runtime, config=config)

    print(f"\n[Result] {result}")
    assert result.success is True
    print("✅ 测试通过")


def test_concurrent_safety():
    """测试并发安全性"""
    print("\n" + "="*60)
    print("测试 2: 并发安全性")
    print("="*60)

    # ✅ 安全：使用不可变类型
    safe_config: RunnableConfig = {
        "configurable": {
            "thread_id": "thread_002",
            "agent_name": "test_agent",  # ✅ 字符串
            "max_iterations": 10  # ✅ 整数
        }
    }

    # ⚠️ 演示：可变类型的问题
    mutable_settings = {"count": 0}  # ⚠️ 共享引用
    unsafe_config: RunnableConfig = {
        "configurable": {
            "thread_id": "thread_003",
            "settings": mutable_settings  # ⚠️ 危险！
        }
    }

    print("[Safe Config]")
    print(f"  - agent_name: {safe_config['configurable']['agent_name']}")
    print(f"  - max_iterations: {safe_config['configurable']['max_iterations']}")
    print("  ✅ 使用不可变类型，并发安全")

    print("\n[Unsafe Config]")
    print(f"  - settings: {unsafe_config['configurable']['settings']}")
    print("  ⚠️ 使用可变对象，多线程可能相互影响")

    # ✅ 推荐：使用 Runtime.context 存储复杂对象
    @dataclass
    class ComplexContext:
        user_id: str
        settings: dict  # 每次传入新实例

    safe_runtime = Runtime(
        context=ComplexContext(
            user_id="user_002",
            settings={"count": 0}  # 每次调用都是新实例
        )
    )

    print("\n[Recommended Approach]")
    print(f"  - 使用 Runtime.context 存储复杂对象")
    print(f"  - user_id: {safe_runtime.context.user_id}")
    print(f"  - settings: {safe_runtime.context.settings}")
    print("  ✅ 每次调用传入新实例，并发安全")


def test_config_merge():
    """测试 config 合并"""
    print("\n" + "="*60)
    print("测试 3: Config 合并")
    print("="*60)

    # 原始 config
    original_config: RunnableConfig = {
        "configurable": {
            "thread_id": "thread_004",
            "checkpoint_ns": ""
        },
        "metadata": {
            "environment": "production"
        }
    }

    print("[Original Config]")
    print(f"  {json.dumps(original_config, indent=2, ensure_ascii=False)}")

    # ✅ 正确合并
    try:
        from langgraph._internal._config import patch_configurable
        merged_config = patch_configurable(
            original_config,
            {"agent_name": "business_intent_agent"}
        )
        print("\n[Merged Config - Using patch_configurable]")
        print(f"  {json.dumps(merged_config, indent=2, ensure_ascii=False)}")
        print("  ✅ 保留了原有的 thread_id 和 metadata")
    except ImportError:
        # 手动合并
        merged_config = {
            **original_config,
            "configurable": {
                **original_config.get("configurable", {}),
                "agent_name": "business_intent_agent"
            }
        }
        print("\n[Merged Config - Manual merge]")
        print(f"  {json.dumps(merged_config, indent=2, ensure_ascii=False)}")
        print("  ✅ 手动合并也可以")

    # ❌ 错误做法
    wrong_config = {
        "configurable": {"agent_name": "business_intent_agent"}
    }
    print("\n[Wrong Config - Overwrite]")
    print(f"  {json.dumps(wrong_config, indent=2, ensure_ascii=False)}")
    print("  ❌ 丢失了原有的 thread_id 和 metadata")


# ==================== 6. 运行测试 ====================

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# Runtime 和 Config 使用示例")
    print("#"*60)

    test_basic_usage()
    test_concurrent_safety()
    test_config_merge()

    print("\n" + "="*60)
    print("所有测试完成！查看 agent_logs.jsonl 文件查看日志")
    print("="*60)

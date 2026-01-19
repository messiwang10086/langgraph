"""
独立可运行的测试示例（不依赖 LangChain/LangGraph）
展示 Runtime 和 Config 的核心概念
"""

from typing import TypedDict, Any, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
import json

# ==================== 1. 模拟 LangGraph 类型 ====================

# 模拟 RunnableConfig
RunnableConfig = Dict[str, Any]


@dataclass
class Runtime:
    """模拟 LangGraph Runtime"""
    context: Any = None
    store: Any = None
    stream_writer: Any = None
    previous: Any = None


# ==================== 2. 定义数据结构 ====================

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


# ==================== 3. 日志记录器 ====================

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
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


logger = AgentLogger()


# ==================== 4. Middleware 实现 ====================

def log_agent_start(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig
) -> None:
    """
    ✅ 正确实现：同时接收 runtime 和 config

    关键点：
    1. runtime: 用于访问 context, store 等
    2. config: 用于访问 configurable, metadata 等
    3. ❌ 不能使用 runtime.config（Runtime 没有 config 属性）
    """
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
    runtime: Runtime,
    config: RunnableConfig,
    result: Optional[Any] = None
) -> None:
    """
    ✅ 正确实现：记录 agent_name 和 model_output

    关键点：
    1. 从 config 获取 agent_name（不是 runtime.config）
    2. 从多个来源尝试获取模型输出：
       - result 参数（如果 middleware 支持）
       - state.last_agent_output
       - state.messages 最后一条
    """
    # ✅ 从 config 获取 agent_name
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")

    req_id = state.get("data", {}).get("req_id")
    creation_id = state.get("data", {}).get("creationId")

    # 从 runtime 获取上下文
    user_id = runtime.context.user_id if runtime.context else "unknown"

    # ✅ 提取模型输出（多种方式）
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
            "model_output": model_output  # ✅ 模型输出
        }
    )


# ==================== 5. 辅助函数：Config 合并 ====================

def patch_configurable(config: RunnableConfig, patch: dict) -> RunnableConfig:
    """
    ✅ 合并 configurable 字段，不覆盖原有配置

    这是简化版的实现，实际 LangGraph 源码在：
    libs/langgraph/langgraph/_internal/_config.py:48-56
    """
    if config is None:
        return {"configurable": patch}
    elif "configurable" not in config:
        return {**config, "configurable": patch}
    else:
        return {
            **config,
            "configurable": {
                **config["configurable"],
                **patch
            }
        }


# ==================== 6. Agent 实现 ====================

def business_intent_agent(
    state: AgentState,
    *,
    runtime: Runtime,
    config: RunnableConfig
) -> AgentOutput:
    """
    ✅ 正确实现：使用 patch_configurable 合并配置

    关键点：
    1. 接收 config 参数（不要覆盖）
    2. 使用 patch_configurable 添加 agent_name
    3. 传递合并后的 config 给下游
    """

    # ✅ 使用 patch_configurable 合并配置
    agent_config = patch_configurable(
        config,  # 保留原有的 thread_id, metadata 等
        {"agent_name": "business_intent_agent"}  # 添加 agent_name
    )

    # 记录开始
    log_agent_start(state, runtime, agent_config)

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

    # 更新 state
    state["last_agent_output"] = result

    # 记录结束
    log_agent_end(state, runtime, agent_config, result)

    return result


# ==================== 7. 测试用例 ====================

def test_basic_usage():
    """测试 1: 基本用法"""
    print("\n" + "="*70)
    print("测试 1: 基本用法 - 演示正确的 runtime 和 config 使用")
    print("="*70)

    # 构造 state
    state: AgentState = {
        "data": {
            "req_id": "test_req_001",
            "creationId": "test_creation_001"
        },
        "messages": [],
        "last_agent_output": None
    }

    # ✅ 构造 config（包含 thread_id 等）
    config: RunnableConfig = {
        "configurable": {
            "thread_id": "test_thread_001",
            "checkpoint_ns": ""
        },
        "metadata": {
            "environment": "test",
            "version": "1.0.0"
        }
    }

    # ✅ 构造 runtime（包含 context）
    test_runtime = Runtime(
        context=Context(user_id="test_user_001", environment="test")
    )

    # ✅ 执行 agent
    result = business_intent_agent(state, runtime=test_runtime, config=config)

    print(f"\n[Result]")
    print(f"  - summary: {result.summary}")
    print(f"  - success: {result.success}")
    print("✅ 测试 1 通过\n")


def test_wrong_vs_right():
    """测试 2: 错误 vs 正确的做法对比"""
    print("\n" + "="*70)
    print("测试 2: 错误 vs 正确的做法对比")
    print("="*70)

    original_config: RunnableConfig = {
        "configurable": {
            "thread_id": "thread_002",
            "checkpoint_ns": ""
        },
        "metadata": {
            "user": "alice"
        }
    }

    print("\n[原始 Config]")
    print(json.dumps(original_config, indent=2, ensure_ascii=False))

    # ❌ 错误做法：直接覆盖
    print("\n❌ 错误做法：直接覆盖")
    wrong_config = {
        "configurable": {"agent_name": "my_agent"}
    }
    print(json.dumps(wrong_config, indent=2, ensure_ascii=False))
    print("问题：丢失了 thread_id 和 metadata！")

    # ✅ 正确做法：使用 patch_configurable
    print("\n✅ 正确做法：使用 patch_configurable")
    right_config = patch_configurable(
        original_config,
        {"agent_name": "my_agent"}
    )
    print(json.dumps(right_config, indent=2, ensure_ascii=False))
    print("优点：保留了所有原有配置！")
    print("✅ 测试 2 通过\n")


def test_concurrent_safety():
    """测试 3: 并发安全性"""
    print("\n" + "="*70)
    print("测试 3: 并发安全性 - configurable 中的可变对象问题")
    print("="*70)

    print("\n✅ 安全做法：使用不可变类型")
    safe_config: RunnableConfig = {
        "configurable": {
            "thread_id": "thread_003",
            "agent_name": "test_agent",  # ✅ 字符串（不可变）
            "max_iterations": 10  # ✅ 整数（不可变）
        }
    }
    print(json.dumps(safe_config["configurable"], indent=2, ensure_ascii=False))
    print("说明：字符串和整数是不可变类型，并发安全")

    print("\n⚠️ 危险做法：使用可变对象")
    mutable_settings = {"count": 0}  # ⚠️ 字典是可变的
    unsafe_config: RunnableConfig = {
        "configurable": {
            "thread_id": "thread_004",
            "settings": mutable_settings  # ⚠️ 共享引用！
        }
    }
    print(json.dumps({"settings": mutable_settings}, indent=2, ensure_ascii=False))
    print("问题：多个并发任务会共享同一个字典对象，相互影响！")

    print("\n✅ 推荐做法：使用 Runtime.context 存储复杂对象")
    @dataclass
    class ComplexContext:
        user_id: str
        settings: dict  # 每次传入新实例

    safe_runtime = Runtime(
        context=ComplexContext(
            user_id="user_003",
            settings={"count": 0}  # 每次调用都是新实例
        )
    )
    print(f"  user_id: {safe_runtime.context.user_id}")
    print(f"  settings: {safe_runtime.context.settings}")
    print("说明：每次 invoke 时传入新的 Context 实例，彻底隔离")
    print("✅ 测试 3 通过\n")


def test_middleware_signature():
    """测试 4: Middleware 签名"""
    print("\n" + "="*70)
    print("测试 4: Middleware 签名演示")
    print("="*70)

    print("\n❌ 错误的 middleware 签名:")
    print("""
def log_agent_start(state: AgentState, runtime: Runtime):
    # ❌ 只接收 runtime，没有 config
    agent_name = runtime.config.get("configurable", {}).get("agent_name")
    # AttributeError: 'Runtime' object has no attribute 'config'
    """)

    print("\n✅ 正确的 middleware 签名:")
    print("""
def log_agent_start(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig  # ✅ 必须接收 config
):
    # ✅ 从 config 获取 agent_name
    agent_name = config.get("configurable", {}).get("agent_name")

    # ✅ 从 runtime 获取 context
    user_id = runtime.context.user_id

    # ✅ 从 state 获取业务数据
    req_id = state["data"]["req_id"]
    """)
    print("✅ 测试 4 通过\n")


# ==================== 8. 运行测试 ====================

if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# Runtime 和 Config 使用示例")
    print("# 演示如何正确使用 Runtime 和 Config，避免常见错误")
    print("#"*70)

    test_basic_usage()
    test_wrong_vs_right()
    test_concurrent_safety()
    test_middleware_signature()

    print("="*70)
    print("所有测试完成！")
    print("查看 agent_logs.jsonl 文件查看完整日志")
    print("="*70)
    print("\n关键要点总结:")
    print("1. ✅ Runtime 用于 context, store 等，Config 用于 configurable, metadata")
    print("2. ✅ Middleware 必须同时接收 runtime 和 config 参数")
    print("3. ✅ 使用 patch_configurable 合并配置，不要直接覆盖")
    print("4. ✅ configurable 中只用不可变类型，复杂对象用 Runtime.context")
    print("5. ✅ 从 config 获取 agent_name，从 runtime 获取 context")

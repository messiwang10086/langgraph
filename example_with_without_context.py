"""
对比示例：有 Context vs 没有 Context
演示何时需要 Context，何时不需要
"""

from typing import TypedDict, Any
from dataclasses import dataclass
from langgraph.graph import StateGraph, START, END
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig

print("\n" + "="*70)
print("示例对比：有 Context vs 没有 Context")
print("="*70)

# ============================================================================
# 示例 1: 不需要 Context（最常见场景）
# ============================================================================

print("\n" + "─"*70)
print("示例 1: 不需要 Context - 简单的数据处理")
print("─"*70)

class SimpleState(TypedDict):
    message: str
    result: str

def simple_agent(state: SimpleState) -> dict:
    """
    ✅ 简单的节点，只处理 State 中的数据
    不需要外部依赖，不需要 Context
    """
    message = state["message"]
    return {"result": f"处理了: {message.upper()}"}

# ✅ 创建 Graph 时不需要 context_schema
simple_graph = StateGraph(state_schema=SimpleState)
simple_graph.add_node("agent", simple_agent)
simple_graph.add_edge(START, "agent")
simple_graph.add_edge("agent", END)
simple_compiled = simple_graph.compile()

# ✅ 调用时不需要 context 参数
print("\n[调用] 不传 context:")
result1 = simple_compiled.invoke({"message": "hello world"})
print(f"输入: {{'message': 'hello world'}}")
print(f"输出: {result1}")
print("✅ 不需要 Context，代码更简单")

# ============================================================================
# 示例 2: 使用 Config.configurable（简单标识符）
# ============================================================================

print("\n" + "─"*70)
print("示例 2: 使用 Config.configurable - 简单配置标识")
print("─"*70)

class StateWithConfig(TypedDict):
    message: str
    result: str

def agent_with_config(state: StateWithConfig, *, config: RunnableConfig) -> dict:
    """
    ✅ 需要简单的配置标识（agent_name, thread_id 等）
    使用 config.configurable，不需要 Context
    """
    message = state["message"]
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")

    return {
        "result": f"[{agent_name}@{thread_id}] 处理了: {message}"
    }

# ✅ 创建 Graph 时不需要 context_schema
config_graph = StateGraph(state_schema=StateWithConfig)
config_graph.add_node("agent", agent_with_config)
config_graph.add_edge(START, "agent")
config_graph.add_edge("agent", END)
config_compiled = config_graph.compile()

# ✅ 调用时传入 config（不是 context）
print("\n[调用] 传入 config:")
result2 = config_compiled.invoke(
    {"message": "hello world"},
    config={
        "configurable": {
            "agent_name": "alice_agent",
            "thread_id": "thread_001"
        }
    }
)
print(f"输入: {{'message': 'hello world'}}")
print(f"配置: agent_name='alice_agent', thread_id='thread_001'")
print(f"输出: {result2}")
print("✅ 简单标识用 config.configurable，不需要 Context")

# ============================================================================
# 示例 3: 需要 Context（外部依赖场景）
# ============================================================================

print("\n" + "─"*70)
print("示例 3: 需要 Context - 外部依赖（API Key、数据库等）")
print("─"*70)

# ✅ 定义 Context（运行时依赖）
@dataclass
class AppContext:
    api_key: str
    database_url: str
    user_id: str

class StateWithContext(TypedDict):
    message: str
    result: str

def agent_with_context(
    state: StateWithContext,
    *,
    runtime: Runtime[AppContext],  # ✅ 接收 runtime
    config: RunnableConfig
) -> dict:
    """
    ✅ 需要外部依赖（API Key、数据库连接等）
    使用 runtime.context 获取
    """
    message = state["message"]

    # 从 runtime.context 获取外部依赖
    api_key = runtime.context.api_key
    database_url = runtime.context.database_url
    user_id = runtime.context.user_id

    # 从 config 获取简单配置
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")

    # 模拟使用外部依赖
    simulated_api_call = f"调用 API (key={api_key[:10]}...)"
    simulated_db_query = f"查询数据库 ({database_url})"

    return {
        "result": (
            f"[{agent_name}] 用户 {user_id} 的消息: {message}\n"
            f"  - {simulated_api_call}\n"
            f"  - {simulated_db_query}"
        )
    }

# ✅ 创建 Graph 时指定 context_schema
context_graph = StateGraph(
    state_schema=StateWithContext,
    context_schema=AppContext  # ✅ 指定 Context schema
)
context_graph.add_node("agent", agent_with_context)
context_graph.add_edge(START, "agent")
context_graph.add_edge("agent", END)
context_compiled = context_graph.compile()

# ✅ 调用时传入 context
print("\n[调用] 传入 context 和 config:")
result3 = context_compiled.invoke(
    {"message": "hello world"},
    context=AppContext(  # ✅ 传入 Context
        api_key="sk-1234567890abcdef",
        database_url="postgresql://localhost/mydb",
        user_id="user_alice"
    ),
    config={
        "configurable": {
            "agent_name": "advanced_agent"
        }
    }
)
print(f"输入: {{'message': 'hello world'}}")
print(f"Context: api_key='sk-...', database_url='postgresql://...', user_id='user_alice'")
print(f"Config: agent_name='advanced_agent'")
print(f"输出:\n{result3['result']}")
print("✅ 外部依赖用 Context，简单配置用 config.configurable")

# ============================================================================
# 示例 4: Context 的另一个好处 - 每次调用独立实例（并发安全）
# ============================================================================

print("\n" + "─"*70)
print("示例 4: Context 的并发安全性")
print("─"*70)

@dataclass
class CounterContext:
    counter: dict  # 可变对象，但每次传入新实例

def counter_agent(
    state: SimpleState,
    *,
    runtime: Runtime[CounterContext]
) -> dict:
    """每次调用都有独立的 counter"""
    counter = runtime.context.counter
    counter["count"] = counter.get("count", 0) + 1
    return {"result": f"计数: {counter['count']}"}

counter_graph = StateGraph(state_schema=SimpleState, context_schema=CounterContext)
counter_graph.add_node("agent", counter_agent)
counter_graph.add_edge(START, "agent")
counter_graph.add_edge("agent", END)
counter_compiled = counter_graph.compile()

print("\n[调用 1] 传入新的 Context 实例:")
result4a = counter_compiled.invoke(
    {"message": "test"},
    context=CounterContext(counter={})  # 新实例
)
print(f"输出: {result4a['result']}")

print("\n[调用 2] 传入另一个新的 Context 实例:")
result4b = counter_compiled.invoke(
    {"message": "test"},
    context=CounterContext(counter={})  # 另一个新实例
)
print(f"输出: {result4b['result']}")
print("✅ 每次调用传入新的 Context 实例，互不影响，并发安全")

print("\n" + "⚠️" + "─"*68)
print("对比：如果用 config.configurable 存储可变对象（不推荐）")
print("─"*70)

# ⚠️ 不推荐的做法
shared_counter = {"count": 0}  # ⚠️ 共享的可变对象
config_with_mutable = {
    "configurable": {
        "counter": shared_counter  # ⚠️ 危险！会被共享
    }
}

def unsafe_counter_agent(state: SimpleState, *, config: RunnableConfig) -> dict:
    counter = config["configurable"]["counter"]
    counter["count"] = counter.get("count", 0) + 1
    return {"result": f"计数: {counter['count']}"}

unsafe_graph = StateGraph(state_schema=SimpleState)
unsafe_graph.add_node("agent", unsafe_counter_agent)
unsafe_graph.add_edge(START, "agent")
unsafe_graph.add_edge("agent", END)
unsafe_compiled = unsafe_graph.compile()

print("\n[调用 1] 使用共享的 counter:")
result5a = unsafe_compiled.invoke({"message": "test"}, config=config_with_mutable)
print(f"输出: {result5a['result']}")

print("\n[调用 2] 使用同一个 counter:")
result5b = unsafe_compiled.invoke({"message": "test"}, config=config_with_mutable)
print(f"输出: {result5b['result']}")
print("⚠️ 问题：两次调用共享同一个 counter，相互影响！")

# ============================================================================
# 总结
# ============================================================================

print("\n" + "="*70)
print("总结")
print("="*70)

print("""
1. ✅ 简单数据处理 → 不需要 Context
   - 只处理 State 中的数据
   - 不需要外部依赖
   - 代码最简单

2. ✅ 简单配置标识 → 使用 config.configurable（不是 Context）
   - thread_id, agent_name 等简单标识
   - 必须使用不可变类型（字符串、数字）
   - 不要放可变对象（字典、列表）

3. ✅ 外部依赖 → 使用 Context
   - API Key、密钥
   - 数据库连接、OSS 客户端
   - 多租户场景
   - 每次调用传入新实例，并发安全

决策流程:
  需要 API Key / 数据库 / 外部依赖？
    ├─ 是 → 使用 Context
    └─ 否 → 需要简单配置？
            ├─ 是 → 使用 config.configurable
            └─ 否 → 不需要任何额外参数
""")

print("="*70)

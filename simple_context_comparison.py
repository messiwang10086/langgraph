"""
简化版对比：有 Context vs 没有 Context
不依赖 LangGraph，纯 Python 演示概念
"""

from typing import TypedDict, Any
from dataclasses import dataclass

print("\n" + "="*70)
print("Context 使用场景对比（简化演示）")
print("="*70)

# ============================================================================
# 场景 1: 不需要 Context - 只处理业务数据
# ============================================================================

print("\n" + "─"*70)
print("场景 1: 不需要 Context - 只处理 State 中的数据")
print("─"*70)

class SimpleState(TypedDict):
    req_id: str
    message: str

def simple_agent_without_context(state: SimpleState) -> dict:
    """
    ✅ 最简单的场景：只处理 State 中的数据
    不需要任何额外的参数
    """
    req_id = state["req_id"]
    message = state["message"]
    result = f"处理请求 {req_id}: {message.upper()}"
    return {"result": result}

# 调用
state1 = {"req_id": "req_001", "message": "hello world"}
result1 = simple_agent_without_context(state1)
print(f"输入: {state1}")
print(f"输出: {result1}")
print("✅ 不需要 Context，不需要 config，代码最简单")

# ============================================================================
# 场景 2: 需要简单配置 - 使用 config.configurable
# ============================================================================

print("\n" + "─"*70)
print("场景 2: 需要简单配置 - 使用 config.configurable")
print("─"*70)

# 模拟 RunnableConfig 类型
RunnableConfig = dict[str, Any]

def agent_with_config(state: SimpleState, *, config: RunnableConfig) -> dict:
    """
    ✅ 需要简单的配置标识（agent_name, thread_id 等）
    使用 config.configurable
    """
    req_id = state["req_id"]
    message = state["message"]

    # 从 config 获取简单配置
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")

    result = f"[{agent_name}@{thread_id}] 处理请求 {req_id}: {message}"
    return {"result": result}

# 调用
state2 = {"req_id": "req_002", "message": "hello"}
config2 = {
    "configurable": {
        "agent_name": "business_intent_agent",
        "thread_id": "thread_001"
    }
}
result2 = agent_with_config(state2, config=config2)
print(f"输入: {state2}")
print(f"配置: {config2['configurable']}")
print(f"输出: {result2}")
print("✅ 简单标识用 config.configurable")

# ============================================================================
# 场景 3: 需要外部依赖 - 使用 Context
# ============================================================================

print("\n" + "─"*70)
print("场景 3: 需要外部依赖 - 使用 Context")
print("─"*70)

# 定义 Context（运行时依赖）
@dataclass
class AppContext:
    api_key: str
    database_url: str
    oss_endpoint: str
    user_id: str

# 模拟 Runtime
@dataclass
class Runtime:
    context: Any

def agent_with_context(
    state: SimpleState,
    *,
    runtime: Runtime,  # ✅ 接收 runtime
    config: RunnableConfig
) -> dict:
    """
    ✅ 需要外部依赖（API Key、数据库连接等）
    从 runtime.context 获取
    """
    req_id = state["req_id"]
    message = state["message"]

    # ✅ 从 runtime.context 获取外部依赖
    api_key = runtime.context.api_key
    database_url = runtime.context.database_url
    user_id = runtime.context.user_id

    # ✅ 从 config 获取简单配置
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")

    # 模拟使用外部依赖
    result = (
        f"[{agent_name}] 用户 {user_id} 的请求 {req_id}\n"
        f"  - 消息: {message}\n"
        f"  - 使用 API Key: {api_key[:10]}...\n"
        f"  - 连接数据库: {database_url}\n"
        f"  - 执行业务逻辑..."
    )
    return {"result": result}

# 调用
state3 = {"req_id": "req_003", "message": "分析业务规则"}
context3 = AppContext(
    api_key="sk-1234567890abcdefghijklmnopqrstuvwxyz",
    database_url="postgresql://localhost/mydb",
    oss_endpoint="https://oss.example.com",
    user_id="alice"
)
runtime3 = Runtime(context=context3)
config3 = {
    "configurable": {
        "agent_name": "business_intent_agent",
        "thread_id": "thread_003"
    }
}
result3 = agent_with_context(state3, runtime=runtime3, config=config3)
print(f"输入: {state3}")
print(f"Context: api_key='{context3.api_key[:10]}...', user_id='{context3.user_id}'")
print(f"Config: {config3['configurable']}")
print(f"输出:\n{result3['result']}")
print("✅ 外部依赖用 Context，简单配置用 config")

# ============================================================================
# 场景 4: 为什么不把外部依赖放在 config.configurable？
# ============================================================================

print("\n" + "─"*70)
print("场景 4: 为什么不把外部依赖放在 config.configurable？")
print("─"*70)

print("\n❌ 不推荐：把复杂对象放在 config.configurable")
print("""
class DatabaseConnection:
    def __init__(self):
        self.connection_count = 0

    def query(self):
        self.connection_count += 1
        return f"查询次数: {self.connection_count}"

# ⚠️ 危险：共享的可变对象
shared_db = DatabaseConnection()

config_bad = {
    "configurable": {
        "thread_id": "thread_001",
        "db_conn": shared_db  # ⚠️ 可变对象！
    }
}

# 第一次调用
def agent_bad_1(state, *, config):
    db_conn = config["configurable"]["db_conn"]
    result = db_conn.query()  # connection_count = 1
    return result

# 第二次调用（可能在不同线程）
def agent_bad_2(state, *, config):
    db_conn = config["configurable"]["db_conn"]
    result = db_conn.query()  # connection_count = 2 ⚠️ 受到第一次调用的影响！
    return result

问题：
1. ⚠️ 多次调用共享同一个数据库连接对象
2. ⚠️ 并发时会相互影响
3. ⚠️ connection_count 会累加，不是每次独立的
""")

print("\n✅ 推荐：把复杂对象放在 Context")
print("""
# ✅ 每次调用传入新的 Context 实例
context1 = AppContext(db_conn=DatabaseConnection())  # 新实例
result1 = agent(state, runtime=Runtime(context=context1), config=config)

context2 = AppContext(db_conn=DatabaseConnection())  # 另一个新实例
result2 = agent(state, runtime=Runtime(context=context2), config=config)

优点：
1. ✅ 每次调用都有独立的数据库连接
2. ✅ 并发安全，互不影响
3. ✅ 每个连接的状态都是独立的
""")

# ============================================================================
# 场景 5: 实际演示并发问题
# ============================================================================

print("\n" + "─"*70)
print("场景 5: 实际演示 - config vs context 的并发安全性")
print("─"*70)

# ⚠️ 不安全：使用 config.configurable 存储可变对象
print("\n⚠️ 不安全的做法（共享可变对象）:")
shared_counter = {"count": 0}

def unsafe_agent(state: SimpleState, *, config: RunnableConfig) -> dict:
    counter = config["configurable"]["counter"]
    counter["count"] += 1
    return {"result": f"计数: {counter['count']}"}

config_unsafe = {
    "configurable": {
        "thread_id": "thread_001",
        "counter": shared_counter  # ⚠️ 共享引用
    }
}

print("调用 1:")
result_unsafe_1 = unsafe_agent({"req_id": "req_1", "message": "test"}, config=config_unsafe)
print(f"  结果: {result_unsafe_1}")

print("调用 2:")
result_unsafe_2 = unsafe_agent({"req_id": "req_2", "message": "test"}, config=config_unsafe)
print(f"  结果: {result_unsafe_2}")
print("  ⚠️ 问题：两次调用共享同一个 counter，count 累加了！")

# ✅ 安全：使用 Context，每次传入新实例
print("\n✅ 安全的做法（每次新实例）:")

@dataclass
class CounterContext:
    counter: dict

def safe_agent(state: SimpleState, *, runtime: Runtime) -> dict:
    counter = runtime.context.counter
    counter["count"] = counter.get("count", 0) + 1
    return {"result": f"计数: {counter['count']}"}

print("调用 1:")
context_safe_1 = CounterContext(counter={})  # 新实例
runtime_safe_1 = Runtime(context=context_safe_1)
result_safe_1 = safe_agent({"req_id": "req_1", "message": "test"}, runtime=runtime_safe_1)
print(f"  结果: {result_safe_1}")

print("调用 2:")
context_safe_2 = CounterContext(counter={})  # 另一个新实例
runtime_safe_2 = Runtime(context=context_safe_2)
result_safe_2 = safe_agent({"req_id": "req_2", "message": "test"}, runtime=runtime_safe_2)
print(f"  结果: {result_safe_2}")
print("  ✅ 每次调用传入新的 Context，count 都是独立的！")

# ============================================================================
# 总结
# ============================================================================

print("\n" + "="*70)
print("总结：什么时候需要 Context？")
print("="*70)

print("""
┌─────────────────────────────────────────────────────────────────┐
│ 使用场景决策树                                                    │
└─────────────────────────────────────────────────────────────────┘

你的 Agent 需要什么？
│
├─ 只处理 State 中的数据
│  └─> ✅ 不需要 Context，不需要 config
│       def agent(state): ...
│
├─ 需要简单的配置标识（agent_name, thread_id）
│  └─> ✅ 使用 config.configurable（不是 Context）
│       def agent(state, *, config): ...
│       config = {"configurable": {"agent_name": "...", "thread_id": "..."}}
│       注意：只能放不可变类型（字符串、数字、元组）
│
└─ 需要外部依赖（API Key、数据库连接、OSS 客户端）
   └─> ✅ 使用 Context
       @dataclass
       class Context:
           api_key: str
           db_conn: Any

       def agent(state, *, runtime: Runtime[Context], config): ...

       每次调用传入新的 Context 实例：
       context = Context(api_key="...", db_conn=...)
       graph.invoke(input, context=context, config=config)

┌─────────────────────────────────────────────────────────────────┐
│ 关键区别                                                          │
└─────────────────────────────────────────────────────────────────┘

config.configurable:
  - 用途：简单的配置标识
  - 类型：只能放不可变类型（字符串、数字）
  - 并发：浅拷贝，可变对象会共享 ⚠️
  - 示例：thread_id, agent_name, max_iterations

Runtime.context:
  - 用途：复杂的运行时依赖
  - 类型：可以放任何对象
  - 并发：每次传入新实例，完全隔离 ✅
  - 示例：api_key, db_conn, oss_client

┌─────────────────────────────────────────────────────────────────┐
│ 您的代码需要 Context 吗？                                         │
└─────────────────────────────────────────────────────────────────┘

看看您的 business_intent_agent：

def business_intent_agent(state, *, config):
    req_id = state["data"]["req_id"]           # ← 从 state 获取
    agent_name = config["configurable"]["agent_name"]  # ← 从 config 获取

    # 是否需要 API Key？
    # 是否需要数据库连接？
    # 是否需要 OSS 客户端？

    如果都不需要 → ✅ 不需要 Context
    如果需要     → ✅ 添加 Context

✅ 大部分情况下不需要 Context！
   只有需要外部依赖时才使用 Context。
""")

print("="*70)

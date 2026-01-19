# Context 详解：什么时候需要，什么时候不需要

## 🤔 您的困惑

> "我没太理解 Context 是干嘛的，我都没有在调用的时候显示传递，但是你测试的时候声明了Context"

**答案**: Context 是**可选的**！大多数情况下您根本不需要它。

---

## ✅ 不使用 Context 的例子（最常见）

### 示例 1: 简单的 Agent（不需要 Context）

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class State(TypedDict):
    message: str
    result: str

def my_agent(state: State) -> dict:
    """简单的节点，不需要 Context"""
    return {"result": f"处理了: {state['message']}"}

# ✅ 创建 Graph 时不指定 context_schema
graph = StateGraph(state_schema=State)  # ← 没有 context_schema
graph.add_node("agent", my_agent)
graph.add_edge(START, "agent")
graph.add_edge("agent", END)
compiled = graph.compile()

# ✅ 调用时不传 context
result = compiled.invoke({"message": "hello"})  # ← 没有 context 参数
print(result)  # {"message": "hello", "result": "处理了: hello"}
```

**关键点**:
- ✅ 没有定义 Context 类
- ✅ StateGraph 没有 `context_schema` 参数
- ✅ invoke 时没有 `context` 参数
- ✅ 节点函数只接收 `state`

---

## 🎯 什么时候需要 Context？

Context 用于传递**不属于 State 的运行时依赖**，比如：

### 场景 1: 需要外部依赖（API Key、数据库连接等）

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime
import openai

@dataclass
class Context:
    api_key: str
    db_conn: Any

class State(TypedDict):
    user_query: str
    answer: str

def call_llm_agent(state: State, *, runtime: Runtime[Context]) -> dict:
    """需要 API Key 的节点"""
    # ✅ 从 runtime.context 获取 API Key
    api_key = runtime.context.api_key

    # 调用 OpenAI
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": state["user_query"]}]
    )

    return {"answer": response.choices[0].message.content}

# ✅ 创建 Graph 时指定 context_schema
graph = StateGraph(state_schema=State, context_schema=Context)
graph.add_node("agent", call_llm_agent)
graph.add_edge(START, "agent")
graph.add_edge("agent", END)
compiled = graph.compile()

# ✅ 调用时传入 context
result = compiled.invoke(
    {"user_query": "什么是 LangGraph?"},
    context=Context(api_key="sk-xxx", db_conn=my_db_connection)
)
```

**为什么用 Context 而不是 State?**
- API Key、数据库连接是**运行时依赖**，不是业务状态
- 每次调用可能需要不同的连接（比如多租户）
- 不想污染 State 的业务逻辑

---

### 场景 2: 多租户场景（每次调用不同的用户）

```python
@dataclass
class Context:
    user_id: str
    tenant_id: str
    permissions: list[str]

def check_permission_node(state: State, *, runtime: Runtime[Context]) -> dict:
    """检查权限的节点"""
    user_id = runtime.context.user_id
    permissions = runtime.context.permissions

    if "admin" not in permissions:
        raise PermissionError(f"用户 {user_id} 没有权限")

    return {"status": "authorized"}

# 不同用户调用
result1 = graph.invoke(
    input_data,
    context=Context(user_id="alice", tenant_id="t1", permissions=["admin"])
)

result2 = graph.invoke(
    input_data,
    context=Context(user_id="bob", tenant_id="t2", permissions=["read"])
)
```

---

### 场景 3: 避免并发问题（每次调用新实例）

```python
@dataclass
class Context:
    request_id: str
    start_time: float
    settings: dict  # 每次调用传入新实例

def my_node(state: State, *, runtime: Runtime[Context]) -> dict:
    settings = runtime.context.settings
    settings["count"] += 1  # ✅ 每次调用都是独立的 settings
    return {"result": settings["count"]}

# 每次调用传入新的 Context 实例
result1 = graph.invoke(
    input_data,
    context=Context(
        request_id="req1",
        start_time=time.time(),
        settings={"count": 0}  # 新实例
    )
)

result2 = graph.invoke(
    input_data,
    context=Context(
        request_id="req2",
        start_time=time.time(),
        settings={"count": 0}  # 另一个新实例
    )
)
# ✅ result1 和 result2 互不影响
```

---

## 📊 Context vs Config.configurable vs State

| 特性 | State | Config.configurable | Runtime.Context |
|-----|-------|-------------------|----------------|
| **用途** | 业务状态 | 简单配置标识 | 运行时依赖 |
| **示例** | `user_query`, `result` | `thread_id`, `agent_name` | `api_key`, `db_conn` |
| **数据类型** | 可变可不可变 | **必须不可变** | 可变可不可变 |
| **传递方式** | 节点间传递 | config 参数 | context 参数 |
| **并发安全** | 每个线程独立 State | ⚠️ 浅拷贝，小心可变对象 | ✅ 每次传新实例 |
| **生命周期** | 整个 Graph 执行期间 | 整个 Graph 执行期间 | 单次 invoke 调用 |

---

## 🔍 您的代码中需要 Context 吗？

### ❌ 不需要 Context 的场景

```python
def business_intent_agent(state: AgentState, *, config: RunnableConfig):
    """您的 Agent 可能不需要 Context"""

    # 从 state 获取业务数据
    req_id = state["data"]["req_id"]
    creation_id = state["data"]["creationId"]

    # 从 config 获取配置
    agent_name = config["configurable"]["agent_name"]
    thread_id = config["configurable"]["thread_id"]

    # 执行业务逻辑
    result = do_something(req_id, creation_id)

    return result
```

**判断标准**:
- ✅ 所有需要的数据都在 `state` 中
- ✅ 只需要简单的标识符（agent_name, thread_id）放在 `config.configurable`
- ✅ 没有外部依赖（API Key、数据库连接等）

---

### ✅ 需要 Context 的场景

```python
@dataclass
class Context:
    openai_api_key: str
    oss_client: OSSClient
    db_pool: ConnectionPool

def business_intent_agent(
    state: AgentState,
    *,
    runtime: Runtime[Context],  # ← 添加 runtime
    config: RunnableConfig
):
    """需要外部依赖的 Agent"""

    # 从 state 获取业务数据
    req_id = state["data"]["req_id"]

    # ✅ 从 runtime.context 获取外部依赖
    api_key = runtime.context.openai_api_key
    oss_client = runtime.context.oss_client

    # 调用 LLM
    llm = ChatOpenAI(api_key=api_key)
    result = llm.invoke(...)

    # 保存到 OSS
    oss_client.put_object(...)

    return result

# 调用时传入 context
graph.invoke(
    input_data,
    context=Context(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        oss_client=OSSClient(...),
        db_pool=create_pool(...)
    )
)
```

**判断标准**:
- ✅ 需要 API Key、密钥等敏感信息
- ✅ 需要数据库连接、OSS 客户端等有状态对象
- ✅ 多租户场景，每次调用需要不同的连接

---

## 🎓 测试代码为什么声明了 Context？

我的测试代码声明 Context 是为了**演示完整用法**，但您的实际代码可能不需要：

```python
# 我的测试代码（演示完整用法）
@dataclass
class Context:
    user_id: str = "test_user"

test_runtime = Runtime(context=Context())

result = business_intent_agent(
    test_state,
    runtime=test_runtime,  # 传入 runtime
    config=test_config
)
```

**您的实际代码可以简化为**:

```python
# ✅ 如果不需要 Context，可以这样
def business_intent_agent(state: AgentState, *, config: RunnableConfig):
    # 不接收 runtime 参数
    pass

# 调用时不需要 context
result = graph.invoke(input_data, config={"configurable": {...}})
```

---

## 🛠️ 实践建议

### 1. 大部分情况不需要 Context

```python
# ✅ 简单场景
class State(TypedDict):
    message: str

def my_node(state: State) -> dict:
    return {"message": state["message"].upper()}

graph = StateGraph(State)  # 不需要 context_schema
```

### 2. 需要外部依赖时才用 Context

```python
# ✅ 复杂场景
@dataclass
class Context:
    api_key: str
    db_conn: Any

def my_node(state: State, *, runtime: Runtime[Context]) -> dict:
    api_key = runtime.context.api_key
    # 使用外部依赖...
    return {...}

graph = StateGraph(State, context_schema=Context)
```

### 3. 简单标识用 configurable，复杂对象用 Context

```python
# ✅ 推荐组合
config = {
    "configurable": {
        "thread_id": "thread_001",       # ← 简单标识
        "agent_name": "my_agent"         # ← 简单标识
    }
}

context = Context(
    api_key="sk-xxx",                    # ← 复杂/敏感信息
    db_conn=connection_pool.get_conn()   # ← 有状态对象
)

result = graph.invoke(input_data, config=config, context=context)
```

---

## ✅ 总结

### Context 是什么？
- **可选的运行时依赖注入机制**
- 用于传递 API Key、数据库连接等外部依赖
- 每次 `invoke` 时可以传入不同的实例

### 什么时候不需要 Context？
- ✅ 所有数据都在 State 中
- ✅ 只需要简单配置（用 `config.configurable`）
- ✅ 没有外部依赖

### 什么时候需要 Context？
- ✅ 需要 API Key、密钥
- ✅ 需要数据库连接、OSS 客户端
- ✅ 多租户场景
- ✅ 避免可变对象的并发问题

### 您的代码需要吗？
**大概率不需要**！如果您的 Agent 只是处理 State 中的数据，不需要外部依赖，那就不需要 Context。

---

## 📝 快速决策流程

```
需要 API Key / 数据库连接 / 外部依赖？
│
├─ 是 → 使用 Runtime.Context
│         └─ @dataclass class Context: ...
│         └─ def node(state, *, runtime: Runtime[Context]): ...
│         └─ graph.invoke(input, context=Context(...))
│
└─ 否 → 不需要 Context
          └─ def node(state): ...  或
          └─ def node(state, *, config: RunnableConfig): ...
          └─ graph.invoke(input)  或
          └─ graph.invoke(input, config={...})
```

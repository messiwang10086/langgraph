# Config 传播流程图

## 📊 完整传播流程

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Graph 执行                                                    │
│                                                                  │
│ graph.invoke(                                                    │
│     input,                                                       │
│     config = {                                                   │
│         "configurable": {                                        │
│             "thread_id": "thread_001",                           │
│             "checkpoint_ns": ""                                  │
│         },                                                       │
│         "metadata": {                                            │
│             "environment": "production"                          │
│         }                                                        │
│     }                                                            │
│ )                                                                │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Agent 函数接收                                                │
│                                                                  │
│ def business_intent_agent(                                       │
│     state: AgentState,                                           │
│     *,                                                           │
│     runtime: Runtime,      # Runtime.context, store, etc.       │
│     config: RunnableConfig # ← 接收原始 config                   │
│ ):                                                               │
│                                                                  │
│     # ✅ 使用 patch_configurable 合并                            │
│     agent_config = patch_configurable(                           │
│         config,  # 保留 thread_id, metadata                     │
│         {"agent_name": "business_intent_agent"}  # 添加新字段    │
│     )                                                            │
│                                                                  │
│     # 现在 agent_config = {                                      │
│     #     "configurable": {                                      │
│     #         "thread_id": "thread_001",     ← 保留              │
│     #         "checkpoint_ns": "",           ← 保留              │
│     #         "agent_name": "business_intent_agent"  ← 新增      │
│     #     },                                                     │
│     #     "metadata": {                      ← 保留              │
│     #         "environment": "production"                        │
│     #     }                                                      │
│     # }                                                          │
│                                                                  │
│     agent.invoke(input, agent_config)                            │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Middleware 接收                                               │
│                                                                  │
│ @before_agent                                                    │
│ def log_agent_start(                                             │
│     state: AgentState,                                           │
│     runtime: Runtime,      # Runtime 对象                        │
│     config: RunnableConfig # ← 接收合并后的 config               │
│ ):                                                               │
│     # ✅ 从 config 获取所有信息                                   │
│     agent_name = config["configurable"]["agent_name"]            │
│     # → "business_intent_agent"                                  │
│                                                                  │
│     thread_id = config["configurable"]["thread_id"]              │
│     # → "thread_001"                                             │
│                                                                  │
│     environment = config["metadata"]["environment"]              │
│     # → "production"                                             │
│                                                                  │
│     # ✅ 从 runtime 获取 context                                  │
│     user_id = runtime.context.user_id                            │
│                                                                  │
│     # ✅ 从 state 获取业务数据                                    │
│     req_id = state["data"]["req_id"]                             │
│                                                                  │
│     logger.log("agent_start", agent_name, {...})                 │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. 日志输出                                                       │
│                                                                  │
│ {                                                                │
│   "timestamp": "2026-01-19T10:00:00",                            │
│   "event_type": "agent_start",                                   │
│   "agent_name": "business_intent_agent",  ← ✅ 正确记录           │
│   "thread_id": "thread_001",              ← ✅ 正确记录           │
│   "req_id": "...",                                               │
│   "user_id": "..."                                               │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## ❌ 错误做法：覆盖 config

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Graph 执行                                                    │
│                                                                  │
│ config = {                                                       │
│     "configurable": {"thread_id": "thread_001"},                 │
│     "metadata": {"environment": "production"}                    │
│ }                                                                │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Agent 函数 ❌ 覆盖                                             │
│                                                                  │
│ def business_intent_agent(state, *, runtime, config):            │
│     config = {  # ❌ 覆盖了参数！                                 │
│         "configurable": {"agent_name": "business_intent_agent"}  │
│     }                                                            │
│     # ❌ 现在 config 只有:                                        │
│     # {                                                          │
│     #     "configurable": {"agent_name": "..."}                  │
│     # }                                                          │
│     # 丢失了 thread_id 和 metadata！                              │
│                                                                  │
│     agent.invoke(input, config)                                  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Middleware 接收                                               │
│                                                                  │
│ def log_agent_start(state, runtime, config):                     │
│     agent_name = config["configurable"]["agent_name"]            │
│     # → "business_intent_agent" ✅                               │
│                                                                  │
│     thread_id = config["configurable"]["thread_id"]              │
│     # → KeyError: 'thread_id' ❌                                 │
│                                                                  │
│     environment = config["metadata"]["environment"]              │
│     # → KeyError: 'metadata' ❌                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Runtime 和 Config 的职责分工

```
┌────────────────────────────────────────────────────────────────┐
│                         执行上下文                              │
└────────────────────────────────────────────────────────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        │                                             │
        ▼                                             ▼
┌──────────────────┐                       ┌──────────────────┐
│  Runtime 对象    │                       │  Config 对象      │
├──────────────────┤                       ├──────────────────┤
│ • context        │                       │ • configurable   │
│   └─ 运行时上下文 │                       │   └─ 配置参数     │
│   └─ user_id     │                       │   └─ thread_id   │
│   └─ db_conn     │                       │   └─ agent_name  │
│                  │                       │                  │
│ • store          │                       │ • metadata       │
│   └─ 持久化存储   │                       │   └─ 元数据       │
│                  │                       │   └─ environment │
│ • stream_writer  │                       │   └─ version     │
│   └─ 自定义流输出 │                       │                  │
│                  │                       │ • callbacks      │
│ • previous       │                       │   └─ 回调函数     │
│   └─ 上次返回值   │                       │                  │
│                  │                       │ • tags           │
│ ❌ config        │                       │   └─ 标签列表     │
│   (不存在!)      │                       │                  │
└──────────────────┘                       └──────────────────┘
        │                                             │
        │                                             │
        ▼                                             ▼
┌────────────────────┐                   ┌────────────────────┐
│ 使用场景            │                   │ 使用场景            │
├────────────────────┤                   ├────────────────────┤
│ • 复杂对象          │                   │ • 简单标识符        │
│ • 数据库连接        │                   │ • 线程 ID           │
│ • 自定义配置类      │                   │ • Agent 名称        │
│ • 每次传入新实例    │                   │ • 元数据标签        │
│ • 并发安全          │                   │ • 不可变类型        │
└────────────────────┘                   └────────────────────┘
```

---

## 🎯 数据访问模式

### Middleware 中访问不同来源的数据

```python
@before_agent
def log_agent_start(
    state: AgentState,      # 业务状态
    runtime: Runtime,       # 运行时
    config: RunnableConfig  # 配置
):
    # 📦 从 State 获取：业务数据
    req_id = state["data"]["req_id"]
    creation_id = state["data"]["creationId"]
    messages = state.get("messages", [])

    # 🏃 从 Runtime 获取：运行时上下文
    user_id = runtime.context.user_id
    db_conn = runtime.context.db_conn
    store = runtime.store

    # ⚙️ 从 Config 获取：配置和元数据
    agent_name = config["configurable"]["agent_name"]
    thread_id = config["configurable"]["thread_id"]
    environment = config["metadata"]["environment"]

    # ❌ 不要这样做
    # agent_name = runtime.config["configurable"]["agent_name"]
    # AttributeError: 'Runtime' object has no attribute 'config'
```

---

## 🔀 并发场景下的 Config

### 场景：多个并发请求

```
时间轴 →

Thread 1:  ┌──────────────────────────────────────┐
          │ config = {                           │
          │   "configurable": {                   │
          │     "thread_id": "thread_001",        │
          │     "agent_name": "alice",            │
          │     "settings": shared_dict  ⚠️       │
          │   }                                   │
          │ }                                     │
          └───────────┬──────────────────────────┘
                      │
                      ├─> node1: shared_dict["count"] = 1
                      │
                      └─> node2: shared_dict["count"] = 2

Thread 2:  ┌──────────────────────────────────────┐
          │ config = {                           │
          │   "configurable": {                   │
          │     "thread_id": "thread_002",        │
          │     "agent_name": "bob",              │
          │     "settings": shared_dict  ⚠️       │  ← 共享同一个对象！
          │   }                                   │
          │ }                                     │
          └───────────┬──────────────────────────┘
                      │
                      ├─> node1: shared_dict["count"] = 10
                      │                              ↑
                      └─> node2: 读到的可能是 2 或 10 ⚠️
                                相互影响！

✅ 解决方案：使用不可变类型或 Runtime.context

Thread 1:  runtime = Runtime(context=Context(settings={"count": 0}))
Thread 2:  runtime = Runtime(context=Context(settings={"count": 0}))
          ↑ 每个 Thread 都有独立的 Context 实例
```

---

## 📝 总结

### ✅ 正确模式

```python
# 1. 接收 config
def my_agent(state, *, runtime, config):

# 2. 合并 config
    agent_config = patch_configurable(config, {"agent_name": "..."})

# 3. 传递给下游
    agent.invoke(input, agent_config)

# 4. Middleware 访问
@before_agent
def log(state, runtime, config):
    agent_name = config["configurable"]["agent_name"]  # ✅
    user_id = runtime.context.user_id                  # ✅
    req_id = state["data"]["req_id"]                   # ✅
```

### ❌ 错误模式

```python
# ❌ 覆盖 config
def my_agent(state, *, runtime, config):
    config = {"configurable": {"agent_name": "..."}}  # 丢失了 thread_id

# ❌ 访问 runtime.config
def log(state, runtime, config):
    agent_name = runtime.config["configurable"]["agent_name"]  # AttributeError

# ❌ configurable 中用可变对象
config = {
    "configurable": {
        "settings": {}  # 并发时会相互影响
    }
}
```

---

## 🔗 相关文件

- `README_FIXES.md` - 总览
- `QUICK_FIX_SUMMARY.md` - 快速修复
- `test_example_standalone.py` - 可运行示例

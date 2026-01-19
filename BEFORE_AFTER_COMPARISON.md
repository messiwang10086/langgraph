# 修改前后代码对比

## 📋 问题概述

您的原始代码有两个主要问题：
1. **Middleware 中使用 `runtime.config`** - Runtime 对象没有 config 属性
2. **Agent 函数中覆盖 config** - 导致丢失原有的 thread_id、metadata 等信息

---

## 🔴 问题 1: Middleware 使用 runtime.config

### ❌ 修改前（错误）

```python
@before_agent
def log_agent_start(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """记录 Agent 启动"""
    agent_name = runtime.config.get("configurable", {}).get("agent_name", "unknown")
    # ❌ AttributeError: 'Runtime' object has no attribute 'config'

    metadata = runtime.config.get("metadata", {})
    # ❌ 同样的错误
```

### ✅ 修改后（正确）

```python
@before_agent
def log_agent_start(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig  # ✅ 添加 config 参数
) -> dict[str, Any] | None:
    """记录 Agent 启动"""
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    # ✅ 从 config 获取

    metadata = config.get("metadata", {})
    # ✅ 正确
```

### 📝 修改说明
- **添加 `config: RunnableConfig` 参数**
- **从 `config` 获取 configurable 和 metadata**
- **`runtime` 用于获取 context, store 等**

---

## 🔴 问题 2: 记录模型输出

### ❌ 修改前（不完整）

```python
@after_agent
def log_agent_end(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """记录 Agent 完成"""
    agent_name = runtime.config.get("configurable", {}).get("agent_name", "unknown")
    # ❌ 错误：runtime.config 不存在

    last_agent_output = state.get("last_agent_output")
    # ⚠️ 只从 state 获取，可能不完整

    # ❌ 没有记录模型输出
```

### ✅ 修改后（正确）

```python
@after_agent
def log_agent_end(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig,  # ✅ 添加 config
    result: Any = None  # ✅ 添加 result（如果 middleware 支持）
) -> dict[str, Any] | None:
    """记录 Agent 完成"""
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    # ✅ 从 config 获取

    # ✅ 多来源获取模型输出
    model_output = None

    # 方案 1: 从 result 参数
    if result is not None:
        if isinstance(result, dict):
            model_output = result.get("structured_response") or result
        elif isinstance(result, AgentOutput):
            model_output = {
                "summary": result.summary,
                "success": result.success,
                "error": result.error
            }

    # 方案 2: 从 state.last_agent_output
    if model_output is None:
        last_agent_output = state.get("last_agent_output")
        if last_agent_output is not None:
            model_output = last_agent_output

    # 方案 3: 从 state.messages
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
            "model_output": model_output  # ✅ 记录模型输出
        }
    )
```

### 📝 修改说明
- **添加 `config` 和 `result` 参数**
- **从多个来源尝试获取模型输出**
- **记录 `model_output` 字段**

---

## 🔴 问题 3: Agent 函数覆盖 config

### ❌ 修改前（错误）

```python
def business_intent_agent(state, *, runtime, config: RunnableConfig):
    # 接收了 config 参数，但是...

    config = {  # ❌ 局部变量覆盖了参数！
        "configurable": {"agent_name": "business_intent_agent"}
    }
    # ❌ 丢失了原有的 thread_id、metadata 等

    result = agent.invoke(input, config)
    # ❌ 下游收不到 thread_id
```

### ✅ 修改后（正确）

```python
from langgraph._internal._config import patch_configurable

def business_intent_agent(state, *, runtime, config: RunnableConfig):
    # ✅ 使用 patch_configurable 合并配置
    agent_config = patch_configurable(
        config,  # 保留原有配置（thread_id, metadata 等）
        {"agent_name": "business_intent_agent"}  # 添加新字段
    )
    # ✅ 现在 agent_config 包含所有信息

    result = agent.invoke(input, agent_config)
    # ✅ 下游可以正常获取 thread_id
```

### 📝 修改说明
- **使用 `patch_configurable` 合并配置**
- **不要直接创建新的 config 对象覆盖参数**
- **保留原有的 thread_id、metadata 等信息**

---

## 📊 完整对比表

| 项目 | 修改前 ❌ | 修改后 ✅ |
|------|---------|---------|
| **Middleware 签名** | `(state, runtime)` | `(state, runtime, config)` |
| **获取 agent_name** | `runtime.config["configurable"]["agent_name"]` | `config["configurable"]["agent_name"]` |
| **获取 metadata** | `runtime.config["metadata"]` | `config["metadata"]` |
| **记录模型输出** | 不记录或不完整 | 从多个来源完整获取 |
| **Config 合并** | `config = {...}` 覆盖 | `patch_configurable(config, {...})` 合并 |

---

## 🎯 关键要点

### 1. Runtime vs Config

```python
# ✅ 正确理解
Runtime 对象包含:
  - context: 运行时上下文（user_id, db_conn 等）
  - store: 持久化存储
  - stream_writer: 流输出
  - previous: 上次返回值

Config 对象包含:
  - configurable: 配置字段（thread_id, agent_name 等）
  - metadata: 元数据（environment, version 等）
  - callbacks: 回调函数
  - tags: 标签
```

### 2. 并发安全

```python
# ✅ 安全：不可变类型
config = {
    "configurable": {
        "agent_name": "alice",  # 字符串
        "max_iterations": 10    # 整数
    }
}

# ⚠️ 不安全：可变类型
config = {
    "configurable": {
        "settings": {"count": 0}  # ❌ 字典会被共享
    }
}

# ✅ 推荐：复杂对象用 Runtime.context
runtime = Runtime(
    context=Context(settings={"count": 0})  # 每次传入新实例
)
```

### 3. Config 传递

```python
# ✅ 正确传递流程
1. Graph.invoke(input, config)
   └─> config = {"configurable": {"thread_id": "123"}}

2. Agent 函数接收并合并
   └─> agent_config = patch_configurable(config, {"agent_name": "alice"})
   └─> config = {"configurable": {"thread_id": "123", "agent_name": "alice"}}

3. Middleware 接收完整 config
   └─> thread_id = config["configurable"]["thread_id"]
   └─> agent_name = config["configurable"]["agent_name"]
```

---

## 🧪 测试验证

运行测试以验证修改：

```bash
# 运行独立测试示例
python test_example_standalone.py

# 检查日志文件
cat agent_logs.jsonl | jq '.'
```

**期望输出**:
```json
{
  "event_type": "agent_start",
  "agent_name": "business_intent_agent",  ← ✅ 正确记录
  "thread_id": "test_thread_001"
}
{
  "event_type": "agent_end",
  "agent_name": "business_intent_agent",  ← ✅ 正确记录
  "model_output": {                       ← ✅ 记录模型输出
    "summary": "成功处理请求...",
    "success": true
  }
}
```

---

## 📚 参考文件

- **修正后的 Middleware**: `agent_logger_fixed.py`
- **修正后的 Agent**: `business_intent_agent_fixed.py`
- **完整测试示例**: `test_example_standalone.py`
- **详细迁移指南**: `MIGRATION_GUIDE.md`
- **快速修复总结**: `QUICK_FIX_SUMMARY.md`

# 快速修复总结

## 三个关键修改

### 1️⃣ Middleware: 添加 config 参数

```python
# ❌ 之前（错误）
@before_agent
def log_agent_start(state: AgentState, runtime: Runtime):
    agent_name = runtime.config.get("configurable", {}).get("agent_name")  # ❌ runtime 没有 config
    # ...

# ✅ 之后（正确）
@before_agent
def log_agent_start(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig  # ✅ 添加 config 参数
):
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")  # ✅ 从 config 获取
    # ...
```

---

### 2️⃣ Middleware: 记录模型输出

```python
# ✅ 添加模型输出记录
@after_agent
def log_agent_end(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig,
    result: Any = None  # ← 如果 middleware 支持
):
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")

    # 方案 1: 从 result 获取（如果 middleware 传入）
    model_output = None
    if result is not None:
        if isinstance(result, dict):
            model_output = result.get("structured_response") or result
        else:
            model_output = str(result)

    # 方案 2: 从 state.messages 获取最后一条消息
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
            "model_output": model_output  # ✅ 记录输出
        }
    )
```

---

### 3️⃣ Agent 函数: 正确合并 config

```python
# ❌ 之前（错误）
def business_intent_agent(state, *, runtime, config: RunnableConfig):
    config = {  # ❌ 覆盖了参数！丢失了 thread_id 等信息
        "configurable": {"agent_name": "business_intent_agent"}
    }
    agent.invoke(input, config)

# ✅ 之后（正确）
from langgraph._internal._config import patch_configurable

def business_intent_agent(state, *, runtime, config: RunnableConfig):
    agent_config = patch_configurable(
        config,  # ✅ 保留原有配置
        {"agent_name": "business_intent_agent"}  # ✅ 添加新字段
    )
    agent.invoke(input, agent_config)
```

---

## 并发安全提醒

### ✅ 安全 - 使用不可变类型
```python
config = {
    "configurable": {
        "agent_name": "alice",  # ✅ 字符串
        "max_iterations": 10    # ✅ 整数
    }
}
```

### ⚠️ 危险 - 避免可变类型
```python
config = {
    "configurable": {
        "settings": {"count": 0}  # ⚠️ 字典会被共享！
    }
}
```

### ✅ 复杂对象 - 使用 Runtime.context
```python
from dataclasses import dataclass

@dataclass
class Context:
    agent_name: str
    settings: dict

# 每次调用传入新实例
graph.invoke(
    input,
    context=Context(agent_name="alice", settings={"count": 0})
)
```

---

## 完整工作流程

```
1. Graph 执行时传入 config
   ↓
   config = {"configurable": {"thread_id": "123"}}

2. Agent 函数接收并合并 config
   ↓
   agent_config = patch_configurable(config, {"agent_name": "alice"})
   最终: {"configurable": {"thread_id": "123", "agent_name": "alice"}}

3. Middleware 从 config 获取信息
   ↓
   @before_agent
   def log(state, runtime, config):
       agent_name = config["configurable"]["agent_name"]  # "alice"
       thread_id = config["configurable"]["thread_id"]    # "123"
```

---

## 快速测试

```python
# 测试代码
if __name__ == "__main__":
    test_state = {
        "data": {"req_id": "test_001", "creationId": "creation_001"}
    }

    test_config = {
        "configurable": {"thread_id": "test_thread"}
    }

    test_runtime = Runtime(context=None)

    # 调用
    result = business_intent_agent(
        test_state,
        runtime=test_runtime,
        config=test_config
    )

    # 检查日志文件 agent_logs.jsonl
    # 应该看到：
    # {"event_type": "agent_start", "agent_name": "business_intent_agent", ...}
    # {"event_type": "agent_end", "agent_name": "business_intent_agent", "model_output": "...", ...}
```

---

## 验证清单

- [ ] `runtime.config` 改为 `config`
- [ ] Middleware 添加了 `config: RunnableConfig` 参数
- [ ] Agent 函数使用 `patch_configurable` 而不是覆盖 config
- [ ] `log_agent_end` 记录了 `model_output`
- [ ] configurable 中只有不可变类型（字符串、数字）
- [ ] 测试通过，日志文件包含 agent_name 和 model_output

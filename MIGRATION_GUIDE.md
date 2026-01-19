# Config 和 Runtime 使用修正指南

## 核心问题总结

### ❌ 问题 1: runtime.config 不存在
```python
# ❌ 错误代码
def log_agent_start(state: AgentState, runtime: Runtime):
    agent_name = runtime.config.get("configurable", {}).get("agent_name")
    # AttributeError: 'Runtime' object has no attribute 'config'
```

### ✅ 解决方案: 同时接收 config 参数
```python
# ✅ 正确代码
def log_agent_start(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig  # 添加 config 参数
):
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
```

---

### ❌ 问题 2: 局部变量覆盖函数参数
```python
# ❌ 错误代码
def business_intent_agent(state, *, runtime, config: RunnableConfig):
    # 接收了 config 参数，但是...

    config = {  # ❌ 局部变量覆盖了参数！
        "configurable": {"agent_name": "business_intent_agent"}
    }
    agent.invoke(input, config)  # 丢失了原始 config 的所有信息
```

### ✅ 解决方案: 使用 patch_configurable 合并
```python
# ✅ 正确代码
from langgraph._internal._config import patch_configurable

def business_intent_agent(state, *, runtime, config: RunnableConfig):
    # 合并原有 config 和新的 configurable 字段
    agent_config = patch_configurable(
        config,  # 保留原有的 thread_id、metadata 等
        {"agent_name": "business_intent_agent"}  # 添加新字段
    )
    agent.invoke(input, agent_config)
```

---

## 完整修改清单

### 1. Middleware 修改 (agent_logger_middleware.py)

#### 修改点 1: 添加 config 参数
```python
@before_agent
def log_agent_start(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig  # ← 新增
):
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")
    # ...
```

#### 修改点 2: 记录模型输出
```python
@after_agent
def log_agent_end(
    state: AgentState,
    runtime: Runtime,
    config: RunnableConfig,
    result: Any = None  # ← 新增（如果 middleware 支持）
):
    agent_name = config.get("configurable", {}).get("agent_name", "unknown")

    # 尝试从 result 获取模型输出
    model_output = None
    if result is not None:
        if isinstance(result, dict):
            model_output = result.get("structured_response") or result
        else:
            model_output = str(result)

    # 或者从 state.messages 获取最后一条消息
    messages = state.get("messages", [])
    if messages and len(messages) > 0:
        last_message = messages[-1]
        if isinstance(last_message, dict):
            model_output = last_message.get("content")

    logger.log(
        event_type="agent_end",
        agent_name=agent_name,
        data={
            "req_id": req_id,
            "creation_id": creation_id,
            "model_output": model_output  # ← 新增
        }
    )
```

---

### 2. Agent 函数修改 (business_intent_agent.py)

#### 修改点 1: 接收 config 参数
```python
# ✅ 正确签名
def business_intent_agent(
    state: AgentState,
    *,
    runtime: Runtime,  # 可选，根据需要
    config: RunnableConfig  # ← 必须接收
) -> AgentOutput:
```

#### 修改点 2: 使用 patch_configurable 合并配置
```python
from langgraph._internal._config import patch_configurable

def business_intent_agent(state, *, runtime, config):
    # ✅ 方案 1: 使用 patch_configurable（推荐）
    agent_config = patch_configurable(
        config,  # 原有配置
        {"agent_name": "business_intent_agent"}  # 新增字段
    )

    # ✅ 方案 2: 手动合并（如果不想依赖内部 API）
    # agent_config = {
    #     **config,
    #     "configurable": {
    #         **config.get("configurable", {}),
    #         "agent_name": "business_intent_agent"
    #     }
    # }

    # ✅ 方案 3: 使用 metadata（如果只是标识用途）
    # agent_config = {
    #     **config,
    #     "metadata": {
    #         **config.get("metadata", {}),
    #         "agent_name": "business_intent_agent"
    #     }
    # }

    result = agent.invoke(input, agent_config)
    return result
```

---

## 并发安全性检查

### ✅ 安全的做法
```python
config = {
    "configurable": {
        "thread_id": "thread1",
        "agent_name": "alice",  # ✅ 字符串，不可变
        "max_iterations": 10,   # ✅ 整数，不可变
        "tags": ("tag1", "tag2")  # ✅ 元组，不可变
    }
}
```

### ⚠️ 不安全的做法
```python
config = {
    "configurable": {
        "thread_id": "thread1",
        "settings": {"count": 0},  # ⚠️ 可变字典，共享引用！
        "items": []  # ⚠️ 可变列表，共享引用！
    }
}

# 并发执行时会相互影响
def node(state, *, config):
    settings = config["configurable"]["settings"]
    settings["count"] += 1  # ⚠️ 竞态条件！
```

### ✅ 安全替代方案: 使用 Runtime.context
```python
from dataclasses import dataclass

@dataclass
class AgentContext:
    agent_name: str
    settings: dict  # 每次 invoke 传入新实例

# ✅ 使用 context 而不是 configurable
graph.invoke(
    input_data,
    context=AgentContext(
        agent_name="alice",
        settings={"count": 0}  # 每次都是新实例
    )
)

def node(state, *, runtime: Runtime[AgentContext]):
    # ✅ 每个调用都有独立的 context
    agent_name = runtime.context.agent_name
    settings = runtime.context.settings
```

---

## Runtime vs Config 使用场景

| 场景 | 推荐方案 | 原因 |
|-----|---------|------|
| 简单标识符 (agent_name, user_id) | `config.configurable` | 简单不可变值，适合传播 |
| 复杂对象 (数据库连接, 配置对象) | `runtime.context` | 每次传入新实例，避免共享 |
| 元数据 (标签, 追踪 ID) | `config.metadata` | 专门用于元数据 |
| 持久化存储 | `runtime.store` | LangGraph 内置机制 |
| 自定义流输出 | `runtime.stream_writer` | LangGraph 内置机制 |

---

## 测试代码示例

```python
if __name__ == "__main__":
    from dataclasses import dataclass

    # 定义 Context
    @dataclass
    class Context:
        user_id: str
        db_conn: Any = None

    # 构造测试数据
    test_state: AgentState = {
        "data": {
            "req_id": "test_req_001",
            "creationId": "test_creation_001"
        }
    }

    # ✅ 创建 config（用于简单标识）
    test_config: RunnableConfig = {
        "configurable": {
            "thread_id": "test_thread_001",
            "agent_name": "business_intent_agent"  # 可以预设
        },
        "metadata": {
            "environment": "test",
            "version": "1.0.0"
        }
    }

    # ✅ 创建 runtime（用于复杂对象）
    test_runtime = Runtime(
        context=Context(user_id="test_user", db_conn=None)
    )

    # ✅ 调用 agent
    result = business_intent_agent(
        test_state,
        runtime=test_runtime,
        config=test_config
    )
    print(result)
```

---

## 常见错误和调试

### 错误 1: AttributeError: 'Runtime' object has no attribute 'config'
**原因**: Runtime 没有 config 属性
**解决**: 同时接收 config 参数

### 错误 2: agent_name 总是 "unknown"
**原因**: config 被局部变量覆盖
**解决**: 使用 patch_configurable 合并配置

### 错误 3: 并发时数据相互覆盖
**原因**: configurable 中使用了可变对象
**解决**: 使用不可变类型或 Runtime.context

### 错误 4: middleware 收不到 agent_name
**原因**: middleware 签名缺少 config 参数
**解决**: 添加 config: RunnableConfig 参数

---

## 检查清单

- [ ] Middleware 签名包含 `config: RunnableConfig`
- [ ] 从 `config` 获取 configurable，而不是 `runtime.config`
- [ ] 使用 `patch_configurable` 合并配置，而不是覆盖
- [ ] configurable 中只使用不可变类型（字符串、数字、元组）
- [ ] 复杂对象放在 `runtime.context` 中
- [ ] 测试代码传入了完整的 config 和 runtime

---

## 参考资源

- **Config 合并源码**: `libs/langgraph/langgraph/_internal/_config.py:48-190`
- **Runtime 定义**: `libs/langgraph/langgraph/runtime.py:27-147`
- **Config 传播流程**: `libs/langgraph/langgraph/pregel/_algo.py:676-720`
- **并发安全分析**: `libs/langgraph/langgraph/_internal/_config.py:173-189`

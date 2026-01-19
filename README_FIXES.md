# Runtime 和 Config 使用修正方案

## 📝 问题总结

您的代码有三个关键问题需要修正：

1. ❌ **Middleware 中使用 `runtime.config`** - Runtime 对象没有 config 属性
2. ❌ **Agent 函数覆盖 config** - 丢失了 thread_id 等信息
3. ⚠️ **未记录模型输出** - 日志不完整

## 🚀 快速修复

### 核心修改（3 处）

#### 1. Middleware 添加 config 参数

```python
# ❌ 之前
def log_agent_start(state, runtime):
    agent_name = runtime.config.get("configurable", {}).get("agent_name")

# ✅ 之后
def log_agent_start(state, runtime, config: RunnableConfig):
    agent_name = config.get("configurable", {}).get("agent_name")
```

#### 2. 记录模型输出

```python
@after_agent
def log_agent_end(state, runtime, config, result=None):
    model_output = None
    if result is not None:
        model_output = result
    elif state.get("last_agent_output"):
        model_output = state["last_agent_output"]

    logger.log("agent_end", agent_name, {"model_output": model_output})
```

#### 3. 使用 patch_configurable 合并配置

```python
# ❌ 之前
def business_intent_agent(state, *, runtime, config):
    config = {"configurable": {"agent_name": "xxx"}}  # 覆盖了！

# ✅ 之后
from langgraph._internal._config import patch_configurable

def business_intent_agent(state, *, runtime, config):
    agent_config = patch_configurable(config, {"agent_name": "xxx"})
```

## 📂 文件说明

### 🔧 修正后的代码文件

| 文件 | 说明 |
|-----|------|
| `agent_logger_fixed.py` | 修正后的 Middleware（正确使用 config） |
| `business_intent_agent_fixed.py` | 修正后的 Agent 函数（正确合并 config） |
| `test_example_standalone.py` | **完整可运行的测试示例** ⭐ |

### 📖 文档文件

| 文件 | 说明 |
|-----|------|
| `QUICK_FIX_SUMMARY.md` | **快速修复总结**（最简洁） ⭐ |
| `BEFORE_AFTER_COMPARISON.md` | 修改前后代码对比 |
| `MIGRATION_GUIDE.md` | 详细迁移指南（包含原理、并发安全等） |

### 📊 日志文件

| 文件 | 说明 |
|-----|------|
| `agent_logs.jsonl` | 测试运行生成的日志（包含 agent_name 和 model_output） |

## 🧪 快速验证

### 1. 运行测试
```bash
python test_example_standalone.py
```

### 2. 查看日志
```bash
cat agent_logs.jsonl | jq '.'
```

### 3. 检查输出
应该看到：
```json
{
  "event_type": "agent_start",
  "agent_name": "business_intent_agent",  ← ✅
  "thread_id": "test_thread_001"
}
{
  "event_type": "agent_end",
  "agent_name": "business_intent_agent",  ← ✅
  "model_output": {...}                   ← ✅
}
```

## 🎯 关键要点

### Runtime vs Config

```python
# Runtime 对象
runtime = Runtime(
    context=Context(...),  # 运行时上下文
    store=...,            # 持久化存储
    stream_writer=...,    # 流输出
    previous=...          # 上次返回值
)
# ❌ runtime.config 不存在！

# Config 对象
config = {
    "configurable": {     # 配置字段
        "thread_id": "...",
        "agent_name": "..."
    },
    "metadata": {...}     # 元数据
}
```

### 并发安全

```python
# ✅ 安全
config = {"configurable": {"agent_name": "alice"}}  # 字符串

# ⚠️ 不安全
config = {"configurable": {"settings": {}}}  # 可变字典

# ✅ 推荐
runtime = Runtime(context=Context(settings={}))  # 每次新实例
```

## 📚 推荐阅读顺序

1. **先看**: `QUICK_FIX_SUMMARY.md` - 快速了解 3 个关键修改
2. **对比**: `BEFORE_AFTER_COMPARISON.md` - 看修改前后的代码差异
3. **测试**: `test_example_standalone.py` - 运行测试验证理解
4. **深入**: `MIGRATION_GUIDE.md` - 了解原理和最佳实践

## ✅ 验证清单

修改代码时，请确保：

- [ ] Middleware 签名包含 `config: RunnableConfig`
- [ ] 从 `config` 获取 configurable，不是 `runtime.config`
- [ ] 使用 `patch_configurable` 合并配置
- [ ] `log_agent_end` 记录了 `model_output`
- [ ] configurable 中只用不可变类型（字符串、数字）
- [ ] 复杂对象放在 `runtime.context` 中
- [ ] 测试通过，日志包含 agent_name 和 model_output

## 🆘 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `AttributeError: 'Runtime' object has no attribute 'config'` | Middleware 缺少 config 参数 | 添加 `config: RunnableConfig` |
| `agent_name` 总是 "unknown" | config 被覆盖 | 使用 `patch_configurable` |
| 并发时数据相互覆盖 | configurable 中用了可变对象 | 改用不可变类型或 Runtime.context |
| Middleware 收不到 agent_name | 忘记传递 config | 检查函数签名和调用 |

## 💡 最佳实践

1. **简单标识符** → `config.configurable`（agent_name, user_id）
2. **复杂对象** → `runtime.context`（数据库连接、配置对象）
3. **元数据** → `config.metadata`（标签、追踪 ID）
4. **持久化** → `runtime.store`（LangGraph 内置）

## 📞 需要帮助？

如果遇到问题：
1. 先检查 `test_example_standalone.py` 能否运行
2. 对比 `BEFORE_AFTER_COMPARISON.md` 查看差异
3. 查看 `agent_logs.jsonl` 确认日志格式
4. 参考 `MIGRATION_GUIDE.md` 了解详细原理

---

**核心原则**: Runtime 和 Config 是两个独立的对象，不要混淆！

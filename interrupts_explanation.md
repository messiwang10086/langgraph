# 🔍 LangGraph 中两个层级的 Interrupts 详解

## 📋 快速对比

| 属性 | `StateSnapshot.interrupts` | `PregelTask.interrupts` |
|------|---------------------------|------------------------|
| **位置** | 顶层（snapshot 级别） | 每个 task 内部 |
| **作用** | **待解决的中断**（需要恢复的） | **已执行任务产生的中断**（历史记录） |
| **用途** | 用于恢复 graph 执行 | 用于调试和追踪某个任务的中断历史 |
| **时机** | 当前步骤需要处理的中断 | 任务执行过程中产生的中断 |

---

## 1️⃣ StateSnapshot.interrupts（顶层中断）

### 🎯 作用
**代表当前步骤中"待解决"的中断，用于恢复 graph 的执行。**

### 📝 定义
```python
class StateSnapshot(NamedTuple):
    ...
    interrupts: tuple[Interrupt, ...]
    """Interrupts that occurred in this step that are pending resolution."""
    #  ↑ 关键：pending resolution（待解决）
```

### 💡 使用场景

#### 场景 1：人工确认
```python
from langgraph.types import interrupt

def approval_node(state):
    # 需要人工批准
    interrupt("Please approve this action")
    return state

# Graph 执行会在这里暂停
graph.invoke({"data": "..."}, config)

# 获取待处理的中断
snapshot = graph.get_state(config)
print(snapshot.interrupts)
# 输出: (Interrupt(id="...", value="Please approve this action"),)

# 🔑 恢复执行 - 使用顶层 interrupts 的 id
resume_map = {
    i.id: "Approved by admin"  # 使用 interrupt.id 来恢复
    for i in snapshot.interrupts
}
graph.invoke(Command(resume=resume_map), config)
```

#### 场景 2：多个并发中断
```python
# 假设有两个并行的任务都触发了中断
def task1(state):
    interrupt({"prompt": "Enter name"})
    return state

def task2(state):
    interrupt({"prompt": "Enter email"})
    return state

# 执行后
snapshot = graph.get_state(config)
print(len(snapshot.interrupts))  # 2

# 需要同时处理所有中断
resume_map = {
    i.id: f"User input for {i.value['prompt']}"
    for i in snapshot.interrupts  # 遍历所有待解决的中断
}
graph.invoke(Command(resume=resume_map), config)
```

### 🔑 关键特点
- **可操作性**：用于恢复执行，每个 `interrupt.id` 都可以用来提供恢复值
- **动态性**：每次 `get_state()` 返回的是"当前需要处理"的中断
- **必须性**：如果有多个中断，必须全部提供恢复值才能继续执行

---

## 2️⃣ PregelTask.interrupts（任务级中断）

### 🎯 作用
**记录"特定任务"在执行过程中产生的中断，用于调试和追踪。**

### 📝 定义
```python
class PregelTask(NamedTuple):
    """A Pregel task."""
    id: str
    name: str
    interrupts: tuple[Interrupt, ...] = ()  # 该任务产生的中断
```

### 💡 使用场景

#### 场景 1：调试和日志
```python
snapshot = graph.get_state(config)

# 查看每个任务产生的中断
for task in snapshot.tasks:
    if task.interrupts:
        print(f"任务 {task.name} 产生了 {len(task.interrupts)} 个中断:")
        for interrupt in task.interrupts:
            print(f"  - ID: {interrupt.id}")
            print(f"  - Value: {interrupt.value}")
```

#### 场景 2：多任务中断追踪
```python
# 假设有 3 个并行任务
def task_a(state):
    interrupt("Task A needs input")
    return state

def task_b(state):
    interrupt("Task B needs input")
    return state

def task_c(state):
    # 没有中断
    return state

# 执行后
snapshot = graph.get_state(config)

# 查看哪些任务产生了中断
for task in snapshot.tasks:
    print(f"{task.name}: {len(task.interrupts)} interrupts")
# 输出:
# task_a: 1 interrupts
# task_b: 1 interrupts
# task_c: 0 interrupts

# 注意：顶层 interrupts 包含所有任务的中断
print(f"Total pending interrupts: {len(snapshot.interrupts)}")  # 2
```

### 🔑 关键特点
- **历史记录**：记录任务执行过程中的中断历史
- **调试信息**：帮助理解"哪个任务产生了哪些中断"
- **只读性**：主要用于查看，不用于恢复操作

---

## 🔄 两者的关系

### 数据流向
```
任务执行 → task.interrupts (记录) → snapshot.interrupts (待处理)
                  ↓                          ↓
              调试/追踪                  恢复执行
```

### 实际例子
```python
from langgraph.graph import StateGraph
from langgraph.types import interrupt
from typing import TypedDict

class State(TypedDict):
    value: int

def node1(state):
    interrupt("Node1 needs approval")
    return {"value": state["value"] + 1}

def node2(state):
    interrupt("Node2 needs confirmation")
    return {"value": state["value"] + 1}

builder = StateGraph(State)
builder.add_node("node1", node1)
builder.add_node("node2", node2)
# ... 配置 edges

graph = builder.compile(checkpointer=...)

# 执行
config = {"configurable": {"thread_id": "test"}}
graph.invoke({"value": 0}, config)

# 获取状态
snapshot = graph.get_state(config)

# ============================================================
# 1. 查看每个任务的中断（调试用）
# ============================================================
for task in snapshot.tasks:
    print(f"Task {task.name}:")
    for intr in task.interrupts:
        print(f"  - {intr.value}")
# 输出:
# Task node1:
#   - Node1 needs approval
# Task node2:
#   - Node2 needs confirmation

# ============================================================
# 2. 查看待处理的中断（恢复用）
# ============================================================
print(f"\nPending interrupts: {len(snapshot.interrupts)}")
for intr in snapshot.interrupts:
    print(f"  - ID: {intr.id}, Value: {intr.value}")
# 输出:
# Pending interrupts: 2
#   - ID: xxx, Value: Node1 needs approval
#   - ID: yyy, Value: Node2 needs confirmation

# ============================================================
# 3. 恢复执行（使用顶层 interrupts）
# ============================================================
resume_map = {
    intr.id: f"Approved: {intr.value}"
    for intr in snapshot.interrupts  # 使用顶层的！
}
result = graph.invoke(Command(resume=resume_map), config)
```

---

## 📊 序列化时如何处理

### 完整版本（包含两个层级）
```python
def snapshot_to_dict(snapshot):
    """序列化 StateSnapshot，保留两个层级的 interrupts"""

    return {
        # 任务列表（包含每个任务的中断历史）
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                # ⬇️ 任务级中断（调试用）
                "interrupts": [
                    {"id": i.id, "value": safe_serialize(i.value)}
                    for i in t.interrupts
                ],
            }
            for t in snapshot.tasks
        ],

        # ⬇️ 顶层中断（恢复执行用）
        "interrupts": [
            {"id": i.id, "value": safe_serialize(i.value)}
            for i in snapshot.interrupts
        ],
    }
```

### 为什么两者都需要？

1. **`task.interrupts`**：
   - 用于调试："为什么这个任务失败了？"
   - 用于追踪："这个任务产生了哪些中断？"
   - 用于审计："历史上哪些任务需要人工干预？"

2. **`snapshot.interrupts`**：
   - 用于恢复："如何继续执行 graph？"
   - 用于 UI 展示："用户需要处理哪些待办事项？"
   - 用于自动化："哪些中断可以自动处理？"

---

## 🎯 实际应用建议

### 场景 1：简单 API（只返回待处理的）
```python
# 如果你只需要让用户恢复执行
def get_pending_interrupts(snapshot):
    return {
        "pending_interrupts": [
            {"id": i.id, "message": i.value}
            for i in snapshot.interrupts  # 只用顶层的
        ]
    }
```

### 场景 2：调试 API（返回详细信息）
```python
# 如果你需要调试和追踪
def get_detailed_state(snapshot):
    return {
        "tasks": [
            {
                "name": t.name,
                "status": "interrupted" if t.interrupts else "completed",
                "interrupts": [
                    {"id": i.id, "value": i.value}
                    for i in t.interrupts  # 每个任务的中断
                ]
            }
            for t in snapshot.tasks
        ],
        "pending_actions": [
            {"id": i.id, "value": i.value}
            for i in snapshot.interrupts  # 顶层待处理的
        ]
    }
```

### 场景 3：完整序列化（用于持久化）
```python
# 如果你需要保存完整状态
def full_snapshot_serialization(snapshot):
    return {
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "interrupts": [...],  # ✅ 保留历史
            }
            for t in snapshot.tasks
        ],
        "interrupts": [...],  # ✅ 保留待处理的
    }
```

---

## ✅ 总结

| 使用场景 | 使用哪个 interrupts |
|---------|-------------------|
| **恢复 graph 执行** | `snapshot.interrupts` |
| **展示待办事项给用户** | `snapshot.interrupts` |
| **调试任务失败原因** | `task.interrupts` |
| **追踪哪个任务产生了中断** | `task.interrupts` |
| **审计和日志** | 两者都需要 |
| **完整状态持久化** | 两者都需要 |

**记住**：
- 🔑 `snapshot.interrupts` = **"需要做什么"**（待处理）
- 📋 `task.interrupts` = **"谁做了什么"**（历史记录）

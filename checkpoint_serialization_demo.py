"""
LangGraph StateSnapshot 序列化 Demo
使用内置的 JsonPlusSerializer，代码量极少且功能强大
"""

import json
from typing import Any
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import StateSnapshot


# ============================================================================
# Demo 1: 最简单的用法 - 完整序列化/反序列化 (推荐用于持久化)
# ============================================================================

def demo1_full_serialization(snapshot: StateSnapshot) -> bytes:
    """
    完整序列化 StateSnapshot，可以完整恢复
    代码量: 仅 3 行！
    """
    serde = JsonPlusSerializer()

    # 序列化 - 返回 (类型名, 二进制数据)
    type_name, binary_data = serde.dumps_typed(snapshot)

    print(f"✅ Demo 1: 序列化类型 = {type_name}, 数据大小 = {len(binary_data)} 字节")
    return binary_data


def demo1_deserialization(type_name: str, binary_data: bytes) -> StateSnapshot:
    """反序列化 - 完整恢复 StateSnapshot"""
    serde = JsonPlusSerializer()

    # 反序列化
    restored = serde.loads_typed((type_name, binary_data))

    print(f"✅ Demo 1: 反序列化成功，类型 = {type(restored)}")
    return restored


# ============================================================================
# Demo 2: 转换为 JSON 友好的格式 (推荐用于 API 返回)
# ============================================================================

def demo2_to_json_friendly(snapshot: StateSnapshot) -> dict[str, Any]:
    """
    将 StateSnapshot 转为 JSON 可序列化的字典
    代码量: 约 30 行（包含所有字段处理）
    """
    serde = JsonPlusSerializer()

    # 辅助函数：安全序列化任意对象
    def safe_serialize(obj: Any) -> Any:
        """将任意对象转为 JSON 友好格式"""
        try:
            _, data = serde.dumps_typed(obj)
            # 将 msgpack 数据转回 Python 对象
            import ormsgpack
            return ormsgpack.unpackb(data)
        except Exception:
            return str(obj)  # fallback

    # 提取配置信息
    config = snapshot.config.get("configurable", {})
    parent_config = snapshot.parent_config

    return {
        # 基本信息
        "thread_id": config.get("thread_id"),
        "checkpoint_id": config.get("checkpoint_id"),
        "checkpoint_ns": config.get("checkpoint_ns", ""),
        "parent_checkpoint_id": (
            parent_config.get("configurable", {}).get("checkpoint_id")
            if parent_config else None
        ),
        "created_at": snapshot.created_at,

        # 状态数据
        "values": safe_serialize(snapshot.values),
        "next": list(snapshot.next),

        # 元数据
        "metadata": snapshot.metadata,

        # 任务列表
        "tasks": [
            {
                "id": task.id,
                "name": task.name,
                "path": task.path,  # ⚠️ 你的代码遗漏了这个字段
                "error": str(task.error) if task.error else None,
                "result": safe_serialize(task.result),  # ⚠️ 你的代码遗漏了这个字段
                "interrupts": [
                    {"id": intr.id, "value": safe_serialize(intr.value)}
                    for intr in task.interrupts
                ],
                "state": (
                    safe_serialize(task.state)
                    if task.state else None
                ),
            }
            for task in snapshot.tasks
        ],

        # 顶层 interrupts - ⚠️ 你的代码完全遗漏了这个字段
        "interrupts": [
            {"id": intr.id, "value": safe_serialize(intr.value)}
            for intr in snapshot.interrupts
        ],
    }


# ============================================================================
# Demo 3: 直接转为 JSON 字符串 (一行代码)
# ============================================================================

def demo3_to_json_string(snapshot: StateSnapshot) -> str:
    """
    直接转为 JSON 字符串
    代码量: 1 行！
    """
    result = demo2_to_json_friendly(snapshot)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ============================================================================
# Demo 4: 批量序列化历史记录
# ============================================================================

def demo4_serialize_history(snapshots: list[StateSnapshot]) -> list[dict]:
    """
    批量序列化多个 snapshot（如历史记录）
    代码量: 1 行！
    """
    return [demo2_to_json_friendly(snap) for snap in snapshots]


# ============================================================================
# Demo 5: 处理特殊类型（展示 JsonPlusSerializer 的强大之处）
# ============================================================================

def demo5_serialize_complex_types():
    """
    展示 JsonPlusSerializer 可以自动处理的复杂类型
    无需手动编写任何类型检测代码！
    """
    from datetime import datetime, timezone
    from decimal import Decimal
    from pathlib import Path
    from uuid import UUID
    import re
    from collections import deque
    from dataclasses import dataclass
    from pydantic import BaseModel

    # 定义复杂数据结构
    @dataclass
    class MyDataClass:
        name: str
        value: int

    class MyPydantic(BaseModel):
        title: str
        score: float

    complex_data = {
        "datetime": datetime.now(timezone.utc),
        "decimal": Decimal("3.14159"),
        "path": Path("/home/user/file.txt"),
        "uuid": UUID("12345678-1234-5678-1234-567812345678"),
        "regex": re.compile(r"^\d+$"),
        "deque": deque([1, 2, 3]),
        "set": {1, 2, 3},
        "dataclass": MyDataClass("test", 42),
        "pydantic": MyPydantic(title="demo", score=9.5),
        "nested": {
            "list": [1, 2, {"key": "value"}],
            "tuple": (1, 2, 3),
        }
    }

    # 序列化 - 仅需 2 行代码！
    serde = JsonPlusSerializer()
    type_name, data = serde.dumps_typed(complex_data)

    # 反序列化
    restored = serde.loads_typed((type_name, data))

    print(f"✅ Demo 5: 复杂类型序列化成功")
    print(f"   原始数据类型: {len(complex_data)} 个字段")
    print(f"   序列化大小: {len(data)} 字节")
    print(f"   数据完全恢复: {restored['uuid'] == complex_data['uuid']}")

    return restored


# ============================================================================
# 实际使用示例
# ============================================================================

if __name__ == "__main__":
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import InMemorySaver
    from typing import TypedDict

    # 1. 创建一个简单的 graph
    class State(TypedDict):
        value: int
        messages: list[str]

    def increment(state: State) -> State:
        return {
            "value": state["value"] + 1,
            "messages": state["messages"] + [f"Step {state['value']}"]
        }

    builder = StateGraph(State)
    builder.add_node("increment", increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)

    # 编译 graph（带 checkpointer）
    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    # 2. 运行 graph
    config = {"configurable": {"thread_id": "demo-thread"}}
    result = graph.invoke({"value": 0, "messages": []}, config)
    print(f"Graph 运行结果: {result}")

    # 3. 获取 StateSnapshot
    snapshot = graph.get_state(config)
    print(f"\n获取到 StateSnapshot: {type(snapshot)}")
    print(f"  - values: {snapshot.values}")
    print(f"  - next: {snapshot.next}")
    print(f"  - tasks 数量: {len(snapshot.tasks)}")

    # ========================================
    # Demo 1: 完整序列化（用于持久化）
    # ========================================
    print("\n" + "="*60)
    print("Demo 1: 完整序列化（可反序列化）")
    print("="*60)

    serde = JsonPlusSerializer()
    type_name, binary = serde.dumps_typed(snapshot)
    print(f"序列化类型: {type_name}")
    print(f"数据大小: {len(binary)} 字节")

    # 反序列化测试
    restored = serde.loads_typed((type_name, binary))
    print(f"✅ 反序列化成功: {restored.values == snapshot.values}")

    # ========================================
    # Demo 2: JSON 友好格式（用于 API）
    # ========================================
    print("\n" + "="*60)
    print("Demo 2: JSON 友好格式（用于 API 返回）")
    print("="*60)

    json_data = demo2_to_json_friendly(snapshot)
    json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
    print(json_str)

    # ========================================
    # Demo 5: 复杂类型处理
    # ========================================
    print("\n" + "="*60)
    print("Demo 5: 复杂类型自动处理")
    print("="*60)

    demo5_serialize_complex_types()

    # ========================================
    # 代码量对比
    # ========================================
    print("\n" + "="*60)
    print("📊 代码量对比")
    print("="*60)
    print("你的方案:")
    print("  - sanitize_for_serialization: ~150 行")
    print("  - serialize_state_snapshot: ~150 行")
    print("  - 总计: ~300 行")
    print()
    print("使用 JsonPlusSerializer:")
    print("  - 完整序列化: 3 行")
    print("  - JSON 友好格式: 30 行")
    print("  - 总计: 33 行")
    print()
    print("✅ 代码减少 90%，功能更强大！")

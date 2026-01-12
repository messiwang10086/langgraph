# LangGraph Custom Polling Endpoint

这个示例展示了如何在 LangGraph 应用中添加自定义轮询端点，用于查询图执行状态。

## 功能特性

自定义轮询 API 提供以下功能：

- **完整的图执行状态** - 查询 thread 的当前执行状态
- **节点级别详情** - 获取每个节点的执行状态、输出和错误信息
- **Checkpoint 跟踪** - 追踪 checkpoint ID 和执行步骤
- **中断处理** - 获取 interrupt 数据（如果有）
- **错误处理** - 详细的错误信息和异常处理
- **历史查询** - 查询 thread 的执行历史

## 文件结构

```
custom_polling_endpoint/
├── webapp.py              # FastAPI 应用，包含自定义路由
├── graph.py               # 示例 LangGraph 图定义
├── langgraph.json         # LangGraph 配置文件
├── requirements.txt       # Python 依赖
├── .env.example          # 环境变量示例
└── README.md             # 本文档
```

## 安装步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
LANGGRAPH_API_URL=http://localhost:2024
```

### 3. 启动服务器

使用 LangGraph CLI 启动开发服务器：

```bash
langgraph dev --no-browser
```

服务器将在 `http://localhost:2024` 启动。

## API 使用说明

### 主轮询端点

#### `GET /api/graph/query/{thread_id}`

查询指定 thread 的图执行状态。

**请求示例：**

```bash
curl http://localhost:2024/api/graph/query/thread_123
```

**响应示例：**

```json
{
  "status": "idle",
  "last_executed_node": "agent",
  "step": 3,
  "checkpoint_id": "1ef4a5b2-3c4d-5e6f-7890-abcdef123456",
  "output": {
    "messages": [
      "Started processing",
      "Processing data",
      "Agent decision made",
      "Process completed"
    ],
    "step_count": 4
  },
  "nodes": [
    {
      "node_name": "start",
      "status": "completed",
      "step": 0,
      "checkpoint_id": "1ef4a...",
      "output": {"messages": ["Started processing"]},
      "error": null
    },
    {
      "node_name": "process",
      "status": "completed",
      "step": 1,
      "checkpoint_id": "2ef5b...",
      "output": {"messages": ["Processing data"]},
      "error": null
    },
    {
      "node_name": "agent",
      "status": "completed",
      "step": 2,
      "checkpoint_id": "3ef6c...",
      "output": {"messages": ["Agent decision made"]},
      "error": null
    },
    {
      "node_name": "end",
      "status": "completed",
      "step": 3,
      "checkpoint_id": "4ef7d...",
      "output": {"messages": ["Process completed"]},
      "error": null
    }
  ],
  "interrupt_data": null,
  "error": null
}
```

**响应字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | Thread 整体状态：`idle`, `busy`, `interrupted`, `error` |
| `last_executed_node` | string | 最后执行完成的节点名称 |
| `step` | integer | 当前执行步骤编号 |
| `checkpoint_id` | string | 当前 checkpoint 的唯一标识符 |
| `output` | object | 当前 thread 的状态/输出数据 |
| `nodes` | array | 所有节点的详细执行信息 |
| `interrupt_data` | array | 中断数据（如果有） |
| `error` | string | 错误信息（如果有） |

**节点信息字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `node_name` | string | 节点名称 |
| `status` | string | 节点状态：`pending`, `completed`, `error` |
| `step` | integer | 节点执行步骤 |
| `checkpoint_id` | string | 节点的 checkpoint ID |
| `output` | object | 节点的输出结果 |
| `error` | string | 节点错误信息（如果有） |

### 历史查询端点

#### `GET /api/graph/query/{thread_id}/history?limit=10`

查询 thread 的执行历史。

**请求参数：**

- `limit` (optional): 返回的 checkpoint 数量，默认 10

**请求示例：**

```bash
curl http://localhost:2024/api/graph/query/thread_123/history?limit=5
```

**响应示例：**

```json
{
  "thread_id": "thread_123",
  "history": [
    {
      "checkpoint_id": "4ef7d...",
      "step": 3,
      "values": {"messages": [...], "step_count": 4},
      "next": [],
      "metadata": {"step": 3, "source": "loop"}
    },
    {
      "checkpoint_id": "3ef6c...",
      "step": 2,
      "values": {"messages": [...], "step_count": 3},
      "next": ["end"],
      "metadata": {"step": 2, "source": "loop"}
    }
  ]
}
```

## 使用场景

### 1. 实时监控图执行

```python
import httpx
import asyncio

async def monitor_execution(thread_id: str):
    """轮询监控图执行状态"""
    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                f"http://localhost:2024/api/graph/query/{thread_id}"
            )
            data = response.json()

            print(f"Status: {data['status']}")
            print(f"Last Node: {data['last_executed_node']}")
            print(f"Step: {data['step']}")

            # 如果执行完成或出错，停止轮询
            if data['status'] in ['idle', 'error']:
                break

            # 每秒轮询一次
            await asyncio.sleep(1)

# 使用示例
await monitor_execution("thread_123")
```

### 2. 检查节点执行状态

```python
async def check_node_status(thread_id: str, node_name: str):
    """检查特定节点的执行状态"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:2024/api/graph/query/{thread_id}"
        )
        data = response.json()

        # 查找特定节点
        for node in data['nodes']:
            if node['node_name'] == node_name:
                print(f"Node: {node['node_name']}")
                print(f"Status: {node['status']}")
                print(f"Output: {node['output']}")
                if node['error']:
                    print(f"Error: {node['error']}")
                return node

        return None
```

### 3. 处理中断

```python
async def handle_interrupts(thread_id: str):
    """处理图执行中的中断"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:2024/api/graph/query/{thread_id}"
        )
        data = response.json()

        if data['status'] == 'interrupted' and data['interrupt_data']:
            print("Detected interrupts:")
            for interrupt in data['interrupt_data']:
                print(f"  ID: {interrupt['id']}")
                print(f"  Value: {interrupt['value']}")

            # 在这里处理中断，例如提供用户输入或继续执行
            return data['interrupt_data']

        return None
```

## 测试端点

### 1. 创建并运行一个 thread

```python
from langgraph_sdk import get_client

async def test_polling():
    async with get_client(url="http://localhost:2024") as client:
        # 创建一个 thread
        thread = await client.threads.create()
        thread_id = thread["thread_id"]

        # 运行图
        run = await client.runs.create(
            thread_id,
            assistant_id="agent",
            input={"messages": [], "step_count": 0}
        )

        # 等待几秒让图执行
        await asyncio.sleep(2)

        # 查询状态
        import httpx
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                f"http://localhost:2024/api/graph/query/{thread_id}"
            )
            print(response.json())
```

### 2. 使用 curl 测试

```bash
# 健康检查
curl http://localhost:2024/

# 使用 LangGraph SDK 创建一个 thread 后，查询状态
curl http://localhost:2024/api/graph/query/YOUR_THREAD_ID

# 查询历史
curl http://localhost:2024/api/graph/query/YOUR_THREAD_ID/history?limit=5
```

## 自定义和扩展

### 添加更多端点

你可以在 `webapp.py` 中添加更多自定义端点：

```python
@app.get("/api/graph/stats/{thread_id}")
async def get_thread_stats(thread_id: str):
    """获取 thread 的统计信息"""
    # 实现你的逻辑
    pass

@app.post("/api/graph/cancel/{thread_id}")
async def cancel_execution(thread_id: str):
    """取消图执行"""
    # 实现你的逻辑
    pass
```

### 修改响应格式

你可以在 `webapp.py` 中修改 `ApiResponse` 和 `NodeInfo` 模型来自定义响应格式：

```python
class CustomNodeInfo(BaseModel):
    """自定义节点信息"""
    name: str
    status: str
    duration: float  # 添加执行时间
    # 添加其他字段
```

### 添加认证

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/api/graph/query/{thread_id}")
async def query_graph_status(
    thread_id: str,
    credentials = Depends(security)
):
    # 验证 token
    if credentials.credentials != "your-secret-token":
        raise HTTPException(status_code=401, detail="Invalid token")
    # 继续处理请求
    ...
```

## 故障排除

### 端点返回 404

确保：
1. LangGraph 服务器正在运行
2. Thread ID 存在且正确
3. `LANGGRAPH_API_URL` 配置正确

### 端点返回 500

检查：
1. LangGraph 服务器日志
2. 网络连接
3. API 权限配置

### 数据格式不匹配

确认：
1. 使用的 LangGraph SDK 版本兼容
2. 图定义正确
3. State 类型定义匹配

## 部署到生产环境

### 使用 Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["langgraph", "start"]
```

### 使用 LangGraph Cloud

```bash
# 部署到 LangGraph Cloud
langgraph deploy
```

## 相关文档

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [LangGraph SDK API 参考](https://langchain-ai.github.io/langgraph/cloud/reference/api/)

## 许可证

此示例代码遵循 MIT 许可证。

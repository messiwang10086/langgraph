from typing import Optional
from langchain.agents.middleware import ToolCallLimitMiddleware, ModelRetryMiddleware
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_agent
import json
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig
from app.core.agent.map_reduce.contracts.agent_io import AgentOutput
from app.core.agent.map_reduce.middleware.agent_logger_middleware import log_agent_start, log_agent_end
from app.core.agent.map_reduce.state.state import AgentState
from app.core.tools.agent_evaluation_tools import get_client
from app.core.tools.business_rules_saver import (
    ToolGlobalConstraints,
    ToolScenariosList,
    ToolUIValidationsList,
    ToolUIInteractionFlowsList,
    assemble_biz_intent_json,
    validate_test_rules
)

# ========== System Prompt 模板 ==========
SYSTEM_PROMPT_TEMPLATE = """
# 角色 (Role)
你是 **BizIntent-Bot**，一位精通业务逻辑拆解的产品分析师。
你的任务是从 PRD 和 UI 设计稿中提取核心业务规则，忽略视觉细节。并保存至oss

# 任务清单 (Checklist)
1.  **用户故事 (User Stories)**: 提取核心的 "Who does What -> Result" 链路。
2.  **数据约束 (Data Rules)**: 提取字段级限制（如：金额>0, 名字长度<20）。
3.  **状态机 (State Machine)**: 提取核心对象的状态流转（如：订单从 Created -> Paid -> Shipped）。
4.  **UI 交互**: 如果有 UI，提取前端校验规则和页面跳转逻辑。

"""


def create_business_intent_tools(state: AgentState):
    """
    工厂函数：根据 state 创建 tools
    优点：闭包自动捕获 state
    """

    # 从 state 中提取需要的数据
    req_id = state["data"].get("req_id")
    creation_id = state["data"].get("creationId")

    @tool
    def business_intent_save(
            global_constraints: Optional[ToolGlobalConstraints],
            scenarios: ToolScenariosList,
            ui_validations: Optional[ToolUIValidationsList],
            ui_interaction_flows: Optional[ToolUIInteractionFlowsList]
    ) -> str:
        """
        对测试规则进行格式校验和重复检测。并保存至oss

        Args:
            global_constraints: 全局约束规则，可选。包含全局性的约束条件列表。
                              例如: {"constraints": ["金额 > 0", "必须登录"]}

            scenarios: 测试场景列表，必填。至少需要包含一个场景，每个场景包含：
                      - name: 场景名称（必填）
                      - flow: 场景流程（必填）
                      - constraints: 场景约束列表（可选）
                      - state_transition: 状态转换（可选）

            ui_validations: UI验证规则列表，可选。如果提供此参数，则对象内部的字段必须完整：
                           - validations: 验证规则列表（允许空列表）
                           - 如果列表不为空，每个规则包含：
                             - element: 验证元素（必填）
                             - rule: 验证规则（必填）

            ui_interaction_flows: UI交互流程列表，可选。如果提供此参数，则对象内部的字段必须完整：
                                 - interaction_flows: 交互流程列表（允许空列表）
                                 - 如果列表不为空，每个流程包含：
                                   - name: 交互流程名称（必填）
                                   - trigger: 触发条件（必填）
                                   - steps: 交互步骤列表（必填，至少一个步骤）
                                   - expected_effect: 预期效果（必填）

        Returns:
            JSON 字符串，包含校验结果
        """
        try:
            result = validate_test_rules(
                global_constraints,
                scenarios,
                ui_validations,
                ui_interaction_flows
            )

            if result.get("status") == "success":
                try:
                    biz_intent_json = assemble_biz_intent_json(result["validated_data"])
                    json_content = json.dumps(biz_intent_json, ensure_ascii=False, indent=2)

                    # 直接使用闭包捕获的变量
                    oss_path = f"test-case-generated/{req_id}/creations/{creation_id}/output/biz_intent.json"

                    client = get_client()
                    oss_result = client.write_content(json_content, oss_path)

                    result["oss_saved"] = True
                    result["oss_path"] = oss_path
                    result["oss_result"] = oss_result

                except Exception as oss_error:
                    result["oss_saved"] = False
                    result["oss_error"] = str(oss_error)

            return json.dumps(result, ensure_ascii=False, indent=4)

        except Exception as e:
            error_response = {
                "status": "error",
                "errors": [f"校验失败: {str(e)}"],
                "error_type": type(e).__name__
            }
            return json.dumps(error_response, ensure_ascii=False, indent=4)

    @tool
    def get_prd_image() -> str:
        """获取 PRD 文档和图片（自动使用当前 state 的 req_id）"""
        # 先返回写死的 PRD 内容 要改成从oss取，同样采用闭包从state获取req_id和creation_id不要暴露方法签名
        return r"""# 工作台 SOP 版本管理 - prd

        ## 页面详情

        ### 页面描述

        | 页面名称 | SOP 版本管理列表 |
        | --- | --- |
        | 模板名称 | 简单列表 |
        | 页面地址 | /lo/sop/page-config |
        | 设计稿 |  |

        ### 页面结构

        初始化：1、解析出 url 参数 `sopKey`。2、调用查询版本列表接口渲染列表。3、调用查询全部版本列表接口查询全部版本（用来初始化新建版本新建版本弹窗下拉框）。

        #### 页头区块

        | **属性名称** | **值** |
        | --- | --- |
        | 返回按钮是否可见 | 是 |
        | 返回 URL | #/unite-sop/lo/sop/list |
        | 主标题 | 版本管理 |

        #### 列表区块

        ##### 操作按钮

        | **按钮名称** | **按钮类型** | **交互说明** |
        | --- | --- | --- |
        | 新建版本 | 主要按钮 | 单击打开弹窗，弹窗标题为：新建版本。 |

        ##### 表格内容

        列名称必须与查询版本列表接口响应参数中的字段含义对应，表格内容：

        | **列名称** | **值展示组件** | **交互说明** |
        | --- | --- | --- |
        | 版本 | 文本 | 交互：版本前加前缀大写字母 `V`，例如：V1。 |
        | 状态 | 标签 | 列宽：120px<br>常量配置：草稿 - draft，线上运行 - publish, 已完成 - finish。<br>颜色值映射逻辑：orange - draft，'#f6493f' - publish， '#f6493f' - publish，green - finish。 |
        | 最后更新人 | 文本 | 列宽：180px<br>格式化说明：最后更新人/最后更新时间，示例：慕冥/2025-12-23 14:33 |
        | 版本描述 | 文本 | 列宽：300px |
        | 列表页 | 超链接组 | 列宽：140px<br>*   链接名称：配置，交互动作：单击打开新页面，页面地址：?hidelayout=true&layoutHiddenMode=all#/unite-sop/lo/{sopKey}/list/edit?version={版本}；草稿状态显示按钮。<br>    <br>*   链接名称：重置，交互动作：单击弹二次确认气泡，接口名称：重置版本；草稿状态显示按钮。<br>    <br>*   链接名称：灰度验证，交互动作：单击打开新页面，页面地址：#/unite-sop/lo/{sopKey}/list/gray?version={版本}；草稿状态显示按钮。<br>    <br>*   链接名称：查看，交互动作：单击打开新页面，页面地址：?hidelayout=true&layoutHiddenMode=all#/unite-sop/lo/{sopKey}/list/view?version={版本}；不是草稿状态显示按钮 |
        | 流程页 | 超链接组1 | 列宽：140px。<br>*   链接名称：配置，交互动作：单击打开新页面，页面地址：?hidelayout=true&layoutHiddenMode=all#/unite-sop/lo/${sopKey}/detail/edit?version={版本}&bizTaskId=；草稿状态显示按钮。<br>    <br>*   链接名称：重置，交互动作：单击弹二次确认气泡，接口名称：重置版本；草稿状态显示按钮。<br>    <br>*   链接名称：灰度验证，交互动作：单击打开新页面，页面地址：#/unite-sop/lo/{sopKey}/detail/gray?version={版本}&bizTaskId=；草稿状态显示按钮。<br>    <br>*   链接名称：查看，交互动作：单击打开新页面，页面地址：?hidelayout=true&layoutHiddenMode=all#/unite-sop/lo/${sopKey}/detail/view?version={版本}&bizTaskId=；不是草稿状态显示按钮。 |
        | 操作列 | 操作列超链接组 | 列宽：230px<br>*   链接名称：发布，交互动作：单击打开发布表单弹窗，弹窗标题：发布版本；草稿状态显示按钮。<br>    <br>*   链接名称：删除，交互动作：单击弹二次确认气泡，接口名称：删除版本；草稿状态显示按钮。按钮样式：危险。<br>    <br>*   链接名称：回滚，交互动作：单击弹二次确认气泡，接口名称：回滚版本；完成状态显示按钮。<br>    <br>*   链接名称：复制创建，交互动作：单击弹二次确认气泡，接口名称：复制创建版本；不是草稿状态显示按钮。<br>    <br>*   链接名称：实例页面，交互动作：单击打开新页面，页面地址：#/unite-sop/lo/{sopKey}/list/online；已发布状态显示按钮。<br>    <br>发布、删除、回滚、复制创建之后都需要调用查询版本列表接口刷新列表页。 |

        #### 弹窗区块1

        ###### 弹窗属性

        | **属性名称** | **属性值** |
        | --- | --- |
        | 弹窗标题 | 发布版本 |
        | 组件名称 | 表单弹窗 |

        ###### 弹窗内容表单区块

        | **字段名称** | **值展示组件** | **是否必填** | **是否可编辑(默认：是)** | **交互说明** |
        | --- | --- | --- | --- | --- |
        | 发布描述 | 文本域 | 否 | 新增时：是 | 字段描述文案：发布信息 |
        | 确定 | 按钮 | - | - | 调用发布接口提交表单内容。<br>提交成功：关闭弹窗，调用查询版本列表接口刷新列表页。<br>提交失败：关闭弹窗，提示用户原因。 |
        | 取消 | 按钮 | - | - | 关闭弹窗 |

        #### 弹窗区块2

        ###### 弹窗属性

        | **属性名称** | **属性值** |
        | --- | --- |
        | 弹窗标题 | 新建版本 |
        | 组件名称 | 表单弹窗 |

        ###### 弹窗内容表单区块

        | **字段名称** | **值展示组件** | **是否必填** | **是否可编辑(默认：是)** | **交互说明** |
        | --- | --- | --- | --- | --- |
        | 版本号 | 下拉框 | 是 | 新增时：是 | 可选项：页面初始化时查到的全部版本列表。数据转换如下格式：[{ label: '新增版本', value: -1 }, 全部版本列表]<br>组件提示文案：请选择版本号 |
        | 确定 | 按钮 | - | - | 调用接口创建版本：<br>*   用户版本号选择的是`新增版本`，调用新建版本接口；版本号选择其他选项调用复制创建版本接口。<br>    <br>*   提交成功：关闭弹窗，调用查询版本列表接口刷新列表页。<br>    <br>*   提交失败：关闭弹窗，提示用户原因。 |
        | 取消 | 按钮 | \- | \- | 关闭弹窗"""

    return [business_intent_save, get_prd_image]


def _create_llm() -> ChatOpenAI:
    """创建 LLM 实例（低 temperature 减少随机性）"""
    llm = ChatOpenAI(
        model="qwen3-coder-plus",
        api_key="5ba5173fee09757d288ac19086187547",
        base_url="https://idealab.alibaba-inc.com/api/openai/v1",
        temperature=0
    )
    return llm


# ✅ 修正：正确处理 config 参数
def business_intent_agent(
    state: AgentState,
    *,
    runtime: Runtime,  # 可以接收但不一定使用
    config: RunnableConfig  # ✅ 从参数获取 config
) -> AgentOutput:
    """核心执行函数"""
    llm = _create_llm()

    # 动态创建包含 state 上下文的 tools
    tools = create_business_intent_tools(state)

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT_TEMPLATE,
        response_format=AgentOutput,
        middleware=[
            ToolCallLimitMiddleware(thread_limit=20, run_limit=10),
            ModelRetryMiddleware(
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
            ),
            log_agent_start,
            log_agent_end
        ]
    )

    # 构建 user prompt
    user_message = (
        "请提取需求。请先调用 get_prd_image 工具获取 PRD 文档，"
        "然后分析并提取业务规则，最后使用 business_intent_save 工具保存结果。"
    )

    # ✅ 方案1：使用 patch_configurable 合并配置（推荐）
    from langgraph._internal._config import patch_configurable

    agent_config = patch_configurable(
        config,  # 使用传入的 config
        {"agent_name": "business_intent_agent"}  # 添加 agent_name
    )

    # ✅ 方案2：如果没有传入 config，手动创建（兼容性方案）
    # if config is None:
    #     agent_config = {
    #         "configurable": {"agent_name": "business_intent_agent"}
    #     }
    # else:
    #     # 合并 configurable
    #     agent_config = {
    #         **config,
    #         "configurable": {
    #             **config.get("configurable", {}),
    #             "agent_name": "business_intent_agent"
    #         }
    #     }

    # 执行 agent
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        agent_config  # ✅ 使用合并后的 config
    )

    # 直接获取结构化输出
    return result["structured_response"]


# ========== 测试入口 ==========
if __name__ == "__main__":
    """本地测试 business_intent_agent"""
    from dataclasses import dataclass

    # 定义一个简单的 Context（如果需要）
    @dataclass
    class Context:
        user_id: str = "test_user"

    # 构造测试用的 state
    test_state: AgentState = {
        "data": {
            "req_id": "test_req_001",
            "creationId": "test_creation_001"
        }
    }

    # ✅ 创建测试用的 config
    test_config: RunnableConfig = {
        "configurable": {
            "thread_id": "test_thread_001"
        }
    }

    # ✅ 创建测试用的 runtime
    test_runtime = Runtime(context=Context())

    # ✅ 调用时传入所有参数
    result = business_intent_agent(
        test_state,
        runtime=test_runtime,
        config=test_config
    )
    print(result)

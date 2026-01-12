"""
Example LangGraph graph for testing the custom polling endpoint.

This is a simple agent graph that demonstrates how the polling
endpoint tracks execution across multiple nodes.
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END


# Define the state
class AgentState(TypedDict):
    """State for the example agent"""
    messages: list[str]
    step_count: int


# Define node functions
def start_node(state: AgentState) -> AgentState:
    """Initial node that starts the process"""
    return {
        "messages": state.get("messages", []) + ["Started processing"],
        "step_count": state.get("step_count", 0) + 1
    }


def process_node(state: AgentState) -> AgentState:
    """Processing node that does some work"""
    return {
        "messages": state.get("messages", []) + ["Processing data"],
        "step_count": state.get("step_count", 0) + 1
    }


def agent_node(state: AgentState) -> AgentState:
    """Agent node that makes decisions"""
    return {
        "messages": state.get("messages", []) + ["Agent decision made"],
        "step_count": state.get("step_count", 0) + 1
    }


def end_node(state: AgentState) -> AgentState:
    """Final node that completes the process"""
    return {
        "messages": state.get("messages", []) + ["Process completed"],
        "step_count": state.get("step_count", 0) + 1
    }


# Build the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("start", start_node)
workflow.add_node("process", process_node)
workflow.add_node("agent", agent_node)
workflow.add_node("end", end_node)

# Add edges
workflow.set_entry_point("start")
workflow.add_edge("start", "process")
workflow.add_edge("process", "agent")
workflow.add_edge("agent", "end")
workflow.add_edge("end", END)

# Compile the graph
graph = workflow.compile()

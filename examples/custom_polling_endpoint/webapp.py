"""
Custom LangGraph Polling API Endpoint

This module provides a custom FastAPI application with a polling endpoint
to query graph execution status, including node-level details.
"""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph_sdk import get_client
import os


# Response models
class NodeInfo(BaseModel):
    """Information about a single node execution"""
    node_name: str
    status: str
    step: int
    checkpoint_id: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ApiResponse(BaseModel):
    """Response model for the graph query endpoint"""
    status: str
    last_executed_node: Optional[str] = None
    step: int
    checkpoint_id: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    nodes: List[NodeInfo] = []
    interrupt_data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


# Create FastAPI app
app = FastAPI(
    title="LangGraph Custom Polling API",
    description="Custom polling endpoint for LangGraph execution status",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "LangGraph Custom Polling API", "status": "running"}


@app.get("/api/graph/query/{thread_id}", response_model=ApiResponse)
async def query_graph_status(thread_id: str):
    """
    Query graph execution status for a specific thread.

    This endpoint retrieves the current state of a graph execution,
    including detailed information about all nodes, checkpoints,
    interrupts, and any errors that occurred.

    Args:
        thread_id: The unique identifier of the thread to query

    Returns:
        ApiResponse: Detailed execution status including:
            - status: Overall thread status (idle, busy, interrupted, error)
            - last_executed_node: Name of the last completed node
            - step: Current execution step number
            - checkpoint_id: Current checkpoint identifier
            - output: Current thread state/output
            - nodes: List of all node execution details
            - interrupt_data: Any interrupt information
            - error: Error message if execution failed

    Raises:
        HTTPException: If thread not found or API error occurs

    Example:
        GET /api/graph/query/thread_123

        Response:
        {
            "status": "idle",
            "last_executed_node": "agent_node",
            "step": 3,
            "checkpoint_id": "1ef4a...",
            "output": {"messages": [...]},
            "nodes": [
                {
                    "node_name": "__start__",
                    "status": "completed",
                    "step": 0,
                    "checkpoint_id": "1ef4a...",
                    "output": {...}
                }
            ],
            "interrupt_data": [],
            "error": null
        }
    """
    try:
        # Get LangGraph API URL from environment or use default
        api_url = os.getenv("LANGGRAPH_API_URL", "http://localhost:2024")

        # Create client to interact with LangGraph API
        async with get_client(url=api_url) as client:
            # Get thread information
            try:
                thread = await client.threads.get(thread_id)
            except Exception as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"Thread not found: {str(e)}"
                )

            # Get current thread state with subgraphs
            try:
                thread_state = await client.threads.get_state(
                    thread_id,
                    subgraphs=True
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get thread state: {str(e)}"
                )

            # Extract checkpoint information
            checkpoint = thread_state.get("checkpoint", {})
            checkpoint_id = checkpoint.get("checkpoint_id")

            # Extract metadata for step information
            metadata = thread_state.get("metadata", {})
            step = metadata.get("step", -1)

            # Extract overall status
            status = thread.get("status", "unknown")

            # Get current state values (output)
            output = thread_state.get("values", {})

            # Process tasks to build node information
            tasks = thread_state.get("tasks", [])
            nodes: List[NodeInfo] = []
            last_executed_node = None
            error_message = None

            for task in tasks:
                node_name = task.get("name", "unknown")
                node_error = task.get("error")
                node_checkpoint = task.get("checkpoint", {})
                node_checkpoint_id = node_checkpoint.get("checkpoint_id") if node_checkpoint else None
                node_state = task.get("state")
                node_result = task.get("result")

                # Determine node status
                if node_error:
                    node_status = "error"
                    error_message = node_error
                elif node_result is not None:
                    node_status = "completed"
                    last_executed_node = node_name
                else:
                    node_status = "pending"

                # Extract step from node state metadata
                node_step = step
                if node_state:
                    node_metadata = node_state.get("metadata", {})
                    node_step = node_metadata.get("step", step)

                nodes.append(NodeInfo(
                    node_name=node_name,
                    status=node_status,
                    step=node_step,
                    checkpoint_id=node_checkpoint_id,
                    output=node_result,
                    error=node_error
                ))

            # Extract interrupt data
            interrupts = thread_state.get("interrupts", [])
            interrupt_data = None
            if interrupts:
                interrupt_data = [
                    {
                        "id": interrupt.get("id"),
                        "value": interrupt.get("value")
                    }
                    for interrupt in interrupts
                ]

            # Build response
            return ApiResponse(
                status=status,
                last_executed_node=last_executed_node,
                step=step,
                checkpoint_id=checkpoint_id,
                output=output,
                nodes=nodes,
                interrupt_data=interrupt_data,
                error=error_message
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/api/graph/query/{thread_id}/history")
async def query_graph_history(thread_id: str, limit: int = 10):
    """
    Query execution history for a thread.

    This endpoint retrieves the checkpoint history for a thread,
    showing the progression of execution over time.

    Args:
        thread_id: The unique identifier of the thread
        limit: Maximum number of checkpoints to return (default: 10)

    Returns:
        List of checkpoint states with metadata

    Raises:
        HTTPException: If thread not found or API error occurs
    """
    try:
        api_url = os.getenv("LANGGRAPH_API_URL", "http://localhost:2024")

        async with get_client(url=api_url) as client:
            # Get thread history
            try:
                history = await client.threads.get_history(
                    thread_id,
                    limit=limit
                )

                return {
                    "thread_id": thread_id,
                    "history": [
                        {
                            "checkpoint_id": state.get("checkpoint", {}).get("checkpoint_id"),
                            "step": state.get("metadata", {}).get("step", -1),
                            "values": state.get("values"),
                            "next": state.get("next"),
                            "metadata": state.get("metadata")
                        }
                        for state in history
                    ]
                }
            except Exception as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"Failed to get thread history: {str(e)}"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

"""
Example client for using the custom polling endpoint.

This module provides a convenient wrapper for the custom polling API,
making it easy to integrate into your applications.
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
import asyncio
import httpx
from enum import Enum


class GraphStatus(str, Enum):
    """Graph execution status"""
    IDLE = "idle"
    BUSY = "busy"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class NodeStatus(str, Enum):
    """Node execution status"""
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class NodeInfo:
    """Node execution information"""
    node_name: str
    status: NodeStatus
    step: int
    checkpoint_id: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class GraphState:
    """Graph execution state"""
    status: GraphStatus
    last_executed_node: Optional[str]
    step: int
    checkpoint_id: Optional[str]
    output: Optional[Dict[str, Any]]
    nodes: List[NodeInfo]
    interrupt_data: Optional[List[Dict[str, Any]]]
    error: Optional[str]


class PollingClient:
    """
    Client for interacting with the custom polling endpoint.

    Example usage:
        async with PollingClient("http://localhost:2024") as client:
            state = await client.get_state("thread_123")
            print(f"Status: {state.status}")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:2024",
        timeout: float = 30.0
    ):
        """
        Initialize the polling client.

        Args:
            base_url: Base URL of the LangGraph API
            timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._client:
            await self._client.aclose()

    async def get_state(self, thread_id: str) -> GraphState:
        """
        Get the current state of a graph execution.

        Args:
            thread_id: The thread ID to query

        Returns:
            GraphState: Current execution state

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(
            f"{self.base_url}/api/graph/query/{thread_id}"
        )
        response.raise_for_status()

        data = response.json()

        # Parse nodes
        nodes = [
            NodeInfo(
                node_name=node["node_name"],
                status=NodeStatus(node["status"]),
                step=node["step"],
                checkpoint_id=node.get("checkpoint_id"),
                output=node.get("output"),
                error=node.get("error")
            )
            for node in data.get("nodes", [])
        ]

        return GraphState(
            status=GraphStatus(data["status"]),
            last_executed_node=data.get("last_executed_node"),
            step=data["step"],
            checkpoint_id=data.get("checkpoint_id"),
            output=data.get("output"),
            nodes=nodes,
            interrupt_data=data.get("interrupt_data"),
            error=data.get("error")
        )

    async def get_history(
        self,
        thread_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get the execution history for a thread.

        Args:
            thread_id: The thread ID to query
            limit: Maximum number of history entries to return

        Returns:
            List of history entries

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(
            f"{self.base_url}/api/graph/query/{thread_id}/history",
            params={"limit": limit}
        )
        response.raise_for_status()

        data = response.json()
        return data.get("history", [])

    async def wait_for_completion(
        self,
        thread_id: str,
        poll_interval: float = 1.0,
        max_attempts: int = 60,
        on_update: Optional[Callable[[GraphState], None]] = None
    ) -> GraphState:
        """
        Wait for graph execution to complete by polling.

        Args:
            thread_id: The thread ID to monitor
            poll_interval: Time to wait between polls (seconds)
            max_attempts: Maximum number of polling attempts
            on_update: Optional callback called on each update

        Returns:
            Final GraphState when execution completes

        Raises:
            TimeoutError: If max_attempts is reached
            httpx.HTTPStatusError: If a request fails
        """
        for attempt in range(max_attempts):
            state = await self.get_state(thread_id)

            if on_update:
                on_update(state)

            # Check if execution is complete
            if state.status in [GraphStatus.IDLE, GraphStatus.ERROR]:
                return state

            # Wait before next poll
            await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"Graph execution did not complete within {max_attempts} attempts"
        )

    async def get_node_by_name(
        self,
        thread_id: str,
        node_name: str
    ) -> Optional[NodeInfo]:
        """
        Get information about a specific node.

        Args:
            thread_id: The thread ID to query
            node_name: Name of the node to find

        Returns:
            NodeInfo if found, None otherwise
        """
        state = await self.get_state(thread_id)

        for node in state.nodes:
            if node.node_name == node_name:
                return node

        return None

    def is_complete(self, state: GraphState) -> bool:
        """
        Check if execution is complete.

        Args:
            state: Graph state to check

        Returns:
            True if execution is complete (idle or error)
        """
        return state.status in [GraphStatus.IDLE, GraphStatus.ERROR]

    def has_errors(self, state: GraphState) -> bool:
        """
        Check if there are any errors in the execution.

        Args:
            state: Graph state to check

        Returns:
            True if there are errors
        """
        if state.error:
            return True

        return any(node.error for node in state.nodes)

    def has_interrupts(self, state: GraphState) -> bool:
        """
        Check if there are any interrupts.

        Args:
            state: Graph state to check

        Returns:
            True if there are interrupts
        """
        return state.interrupt_data is not None and len(state.interrupt_data) > 0


# Example usage functions
async def example_basic_polling():
    """Example: Basic polling for status"""
    async with PollingClient() as client:
        thread_id = "your_thread_id"

        # Get current state
        state = await client.get_state(thread_id)

        print(f"Status: {state.status}")
        print(f"Step: {state.step}")
        print(f"Last node: {state.last_executed_node}")

        # Check completion
        if client.is_complete(state):
            print("✓ Execution complete!")


async def example_wait_for_completion():
    """Example: Wait for execution to complete"""
    async with PollingClient() as client:
        thread_id = "your_thread_id"

        # Define callback for updates
        def on_update(state: GraphState):
            print(f"Status: {state.status}, Step: {state.step}")

        # Wait for completion
        try:
            final_state = await client.wait_for_completion(
                thread_id,
                poll_interval=1.0,
                max_attempts=60,
                on_update=on_update
            )

            print(f"\n✓ Execution finished!")
            print(f"Final status: {final_state.status}")
            print(f"Output: {final_state.output}")

        except TimeoutError:
            print("❌ Execution timed out")


async def example_check_specific_node():
    """Example: Check status of a specific node"""
    async with PollingClient() as client:
        thread_id = "your_thread_id"

        # Get info for specific node
        node = await client.get_node_by_name(thread_id, "agent")

        if node:
            print(f"Node: {node.node_name}")
            print(f"Status: {node.status}")
            print(f"Output: {node.output}")

            if node.error:
                print(f"Error: {node.error}")
        else:
            print("Node not found")


async def example_error_handling():
    """Example: Handle errors and interrupts"""
    async with PollingClient() as client:
        thread_id = "your_thread_id"

        state = await client.get_state(thread_id)

        # Check for errors
        if client.has_errors(state):
            print("⚠️  Errors detected:")
            if state.error:
                print(f"  Global error: {state.error}")

            for node in state.nodes:
                if node.error:
                    print(f"  {node.node_name}: {node.error}")

        # Check for interrupts
        if client.has_interrupts(state):
            print("⚠️  Interrupts detected:")
            for interrupt in state.interrupt_data:
                print(f"  ID: {interrupt['id']}")
                print(f"  Value: {interrupt['value']}")


async def example_query_history():
    """Example: Query execution history"""
    async with PollingClient() as client:
        thread_id = "your_thread_id"

        # Get history
        history = await client.get_history(thread_id, limit=5)

        print(f"History entries: {len(history)}")
        for i, entry in enumerate(history, 1):
            print(f"\nEntry {i}:")
            print(f"  Step: {entry['step']}")
            print(f"  Checkpoint: {entry['checkpoint_id']}")
            print(f"  Next nodes: {entry.get('next', [])}")


if __name__ == "__main__":
    # Run examples
    print("Example usage of PollingClient\n")

    # Uncomment to run specific examples:
    # asyncio.run(example_basic_polling())
    # asyncio.run(example_wait_for_completion())
    # asyncio.run(example_check_specific_node())
    # asyncio.run(example_error_handling())
    # asyncio.run(example_query_history())

    print("See function definitions for usage examples")

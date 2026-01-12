"""
Test script for the custom polling endpoint.

This script demonstrates how to:
1. Create a thread
2. Start a run
3. Poll for status updates
4. Query node-level details
"""

import asyncio
import httpx
from langgraph_sdk import get_client


async def test_polling_endpoint():
    """Test the custom polling endpoint"""

    print("=" * 60)
    print("Testing LangGraph Custom Polling Endpoint")
    print("=" * 60)

    # Configuration
    api_url = "http://localhost:2024"
    assistant_id = "agent"

    async with get_client(url=api_url) as client:
        # Step 1: Create a thread
        print("\n1. Creating a new thread...")
        thread = await client.threads.create()
        thread_id = thread["thread_id"]
        print(f"   Created thread: {thread_id}")

        # Step 2: Start a run
        print("\n2. Starting graph execution...")
        run = await client.runs.create(
            thread_id,
            assistant_id=assistant_id,
            input={
                "messages": [],
                "step_count": 0
            }
        )
        run_id = run["run_id"]
        print(f"   Started run: {run_id}")

        # Step 3: Poll for status using custom endpoint
        print("\n3. Polling for execution status...")
        async with httpx.AsyncClient() as http_client:
            max_attempts = 20
            attempt = 0

            while attempt < max_attempts:
                attempt += 1

                try:
                    # Query custom polling endpoint
                    response = await http_client.get(
                        f"{api_url}/api/graph/query/{thread_id}"
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Display status
                    print(f"\n   Attempt {attempt}:")
                    print(f"   - Status: {data['status']}")
                    print(f"   - Step: {data['step']}")
                    print(f"   - Last Executed Node: {data['last_executed_node']}")

                    # Display node information
                    if data['nodes']:
                        print(f"   - Nodes executed: {len(data['nodes'])}")
                        for node in data['nodes']:
                            print(f"     • {node['node_name']}: {node['status']}")

                    # Check for completion
                    if data['status'] in ['idle', 'error']:
                        print(f"\n   Execution finished with status: {data['status']}")

                        # Display final output
                        if data['output']:
                            print(f"\n   Final output:")
                            print(f"   {data['output']}")

                        # Check for errors
                        if data['error']:
                            print(f"\n   ⚠️  Error: {data['error']}")

                        # Check for interrupts
                        if data['interrupt_data']:
                            print(f"\n   ⚠️  Interrupts detected:")
                            for interrupt in data['interrupt_data']:
                                print(f"      - ID: {interrupt['id']}")
                                print(f"        Value: {interrupt['value']}")

                        break

                    # Wait before next poll
                    await asyncio.sleep(1)

                except httpx.HTTPStatusError as e:
                    print(f"\n   ❌ HTTP Error: {e.response.status_code}")
                    print(f"   {e.response.text}")
                    break
                except Exception as e:
                    print(f"\n   ❌ Error: {str(e)}")
                    break
            else:
                print(f"\n   ⚠️  Max polling attempts reached ({max_attempts})")

        # Step 4: Query execution history
        print("\n4. Querying execution history...")
        async with httpx.AsyncClient() as http_client:
            try:
                response = await http_client.get(
                    f"{api_url}/api/graph/query/{thread_id}/history?limit=5"
                )
                response.raise_for_status()
                history_data = response.json()

                print(f"   Thread: {history_data['thread_id']}")
                print(f"   History entries: {len(history_data['history'])}")

                for i, entry in enumerate(history_data['history'], 1):
                    print(f"\n   Entry {i}:")
                    print(f"   - Checkpoint ID: {entry['checkpoint_id']}")
                    print(f"   - Step: {entry['step']}")
                    print(f"   - Next nodes: {entry.get('next', [])}")

            except Exception as e:
                print(f"   ❌ Error querying history: {str(e)}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


async def test_health_check():
    """Test the health check endpoint"""
    print("\n" + "=" * 60)
    print("Testing Health Check Endpoint")
    print("=" * 60)

    api_url = "http://localhost:2024"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()

            print(f"\n✓ Server is running")
            print(f"  Response: {data}")

        except Exception as e:
            print(f"\n❌ Server not responding: {str(e)}")


async def main():
    """Main test function"""
    try:
        # Test health check first
        await test_health_check()

        # Wait a moment
        await asyncio.sleep(1)

        # Test polling endpoint
        await test_polling_endpoint()

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

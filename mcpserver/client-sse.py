import asyncio
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client

"""
Weather MCP SSE Client

Make sure:
1. The server is running before running this script:
   uv run mcpserver/server.py
2. The server is configured to use SSE transport (default port 8000).
3. Connect specifically to http://localhost:8000/sse
   (Connecting to http://localhost:8000 without /sse will result in a 404 error).
"""


async def main():
    endpoint_url = "http://localhost:8000/sse"
    print(f"Connecting to Weather MCP server at {endpoint_url}...")

    try:
        # Connect to the server using SSE
        async with sse_client(endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the connection
                await session.initialize()

                # List available tools
                tools_result = await session.list_tools()
                print("\nAvailable tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Call our Weather tool
                print("\nFetching weather alerts for CA...")
                result = await session.call_tool("get_alerts", arguments={"state": "CA"})
                if result.content:
                    print(f"\nThe weather alerts are:\n{result.content[0].text}")
                else:
                    print("\nNo content returned.")

    except Exception as exc:
        print(f"\n[Error connecting to MCP server]: {exc}")
        print("\nTroubleshooting tips:")
        print("  1. Ensure the server is running in another terminal:")
        print("     uv run mcpserver/server.py")
        print("  2. Verify you are connecting to '/sse' (http://localhost:8000/sse).")
        print("     Accessing http://localhost:8000 directly will show a web page, not an SSE connection.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
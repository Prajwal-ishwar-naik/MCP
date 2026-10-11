import asyncio
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_path = str(Path(__file__).parent / "server.py")
    # Define server parameters
    server_params = StdioServerParameters(
        command=sys.executable,  # Use the current python interpreter
        args=[server_path, "stdio"],  # Run server with stdio transport
    )

    # Connect to the server
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools_result = await session.list_tools()
            print("Available tools:")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Call our Weather Tool
            print("\nFetching weather alerts for CA...")
            result = await session.call_tool("get_alerts", arguments={"state": "CA"})
            if result.content:
                print(f"\nThe weather alerts are:\n{result.content[0].text}")
            else:
                print("\nNo content returned.")


if __name__ == "__main__":
    asyncio.run(main())
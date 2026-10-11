'''https://github.com/microsoft/playwright-mcp.git'''
import asyncio
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from mcp_use import MCPClient, MCPAgent

# Load environment variables (like GROQ_API_KEY)
load_dotenv()

VALID_SAFE_SEARCH = {"strict", "moderate", "off"}
SEARCH_COOLDOWN_SECONDS = 1.5

AGENT_INSTRUCTIONS = """
When using duckduckgo_web_search:
- Omit safeSearch, or use only lowercase values: strict, moderate, off.
- Never send title-case values like Moderate.

If a search tool fails (invalid args, rate limit, or anomaly), do not retry it.
Use browser_navigate to a news site instead, then answer from the page.
Give the user a useful answer after at most one failed search.
"""


def patch_duckduckgo_search(agent: MCPAgent) -> None:
    """Normalize DuckDuckGo args and avoid back-to-back requests."""
    last_search_at = 0.0

    for tool in agent._tools:
        if tool.name != "duckduckgo_web_search":
            continue

        original_arun = tool._arun

        async def patched_arun(_original=original_arun, **kwargs):
            nonlocal last_search_at
            safe_search = kwargs.get("safeSearch")
            if isinstance(safe_search, str):
                normalized = safe_search.strip().lower()
                if normalized in VALID_SAFE_SEARCH:
                    kwargs["safeSearch"] = normalized
                else:
                    kwargs.pop("safeSearch", None)

            wait_for = SEARCH_COOLDOWN_SECONDS - (time.monotonic() - last_search_at)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            last_search_at = time.monotonic()
            return await _original(**kwargs)

        tool._arun = patched_arun


async def run_memory_chat():
    # Initialize the LLM
    llm = ChatGroq(model="openai/gpt-oss-120b")
    
    # Path to the MCP configuration file
    config_file = "browser_mcp.json"
    
    # Initialize MCP Client and connect to servers defined in JSON
    client = MCPClient(config=config_file)
    
    # Create the agent with LLM and MCP tool access
    agent = MCPAgent(
        llm=llm,
        client=client,
        max_steps=12,
        memory_enabled=True,
        additional_instructions=AGENT_INSTRUCTIONS,
    )
    await agent.initialize()
    patch_duckduckgo_search(agent)
    
    print("AI Assistant Initialized. Type 'exit' or 'quit' to end the chat.\n")
    
    try:
        # Chat loop for interaction
        while True:
            # Using asyncio.to_thread prevents the synchronous input() from blocking the event loop
            user_input = await asyncio.to_thread(input, "You: ")
            
            if user_input.strip().lower() in ["exit", "quit"]:
                print("Shutting down agent...")
                break
                
            if not user_input.strip():
                continue

            try:
                response = await agent.run(user_input)
                print(f"Agent: {response}\n")
            except Exception as exc:
                print(f"Agent error: {exc}\n")
            
    finally:
        # Ensure that connections to the MCP servers are cleanly closed on exit
        await client.close_all_sessions()

# Execution
if __name__ == "__main__":
    try:
        asyncio.run(run_memory_chat())
    except KeyboardInterrupt:
        print("\nSession interrupted by user. Exiting.")

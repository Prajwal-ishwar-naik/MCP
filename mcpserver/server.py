from typing import Any
import sys
import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
from mcp.server.fastmcp import FastMCP


# Create an MCP server
mcp = FastMCP(
    name="weather",
    host="0.0.0.0",  # only used for SSE transport (localhost)
    port=8000,  # only used for SSE transport (set this to any port)
)


@mcp.custom_route("/", methods=["GET"])
async def root(request: Request):
    """
    Provide a friendly landing page at the root URL (/) so that
    visiting http://localhost:8000 doesn't return a 404 Not Found error.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Weather MCP Server</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    max-width: 650px;
                    margin: 50px auto;
                    padding: 24px;
                    line-height: 1.6;
                    background: #0f172a;
                    color: #f8fafc;
                }
                .card {
                    background: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 12px;
                    padding: 28px;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
                }
                h1 { color: #38bdf8; margin-top: 0; font-size: 24px; }
                .status { display: inline-flex; align-items: center; background: #065f46; color: #34d399; padding: 4px 10px; border-radius: 9999px; font-size: 13px; font-weight: 600; margin-bottom: 16px; }
                .status-dot { width: 8px; height: 8px; background: #34d399; border-radius: 50%; margin-right: 6px; }
                code { background: #334155; padding: 3px 8px; border-radius: 6px; color: #38bdf8; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
                ul { padding-left: 20px; }
                li { margin-bottom: 8px; }
                .note { background: #1e3a8a; border-left: 4px solid #60a5fa; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="status"><span class="status-dot"></span> Server Running</div>
                <h1>🌤️ Weather MCP Server</h1>
                <p>The Model Context Protocol (MCP) server is online and ready for connections.</p>
                
                <h3>Connection Endpoints:</h3>
                <ul>
                    <li><strong>SSE Stream URL:</strong> <code>http://localhost:8000/sse</code></li>
                    <li><strong>Messages URL:</strong> <code>http://localhost:8000/messages/</code></li>
                </ul>

                <h3>Available Tools:</h3>
                <ul>
                    <li><code>get_alerts(state: str)</code> - Fetch active weather alerts for a US state (e.g. CA, NY)</li>
                    <li><code>get_forecast(latitude: float, longitude: float)</code> - Get detailed weather forecast</li>
                </ul>

                <div class="note">
                    <strong>Note:</strong> Connect MCP clients directly to <code>http://localhost:8000/sse</code>.
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)

    return JSONResponse({
        "status": "online",
        "name": "weather",
        "description": "Weather MCP Server is running",
        "sse_endpoint": "http://localhost:8000/sse",
        "messages_endpoint": "http://localhost:8000/messages/",
        "tools": ["get_alerts", "get_forecast"],
        "note": "Connect MCP clients to http://localhost:8000/sse"
    })


# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
    Event: {props.get('event', 'Unknown')}
    Area: {props.get('areaDesc', 'Unknown')}
    Severity: {props.get('severity', 'Unknown')}
    Description: {props.get('description', 'No description available')}
    Instructions: {props.get('instruction', 'No specific instructions provided')}
    """

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
                {period['name']}:
                Temperature: {period['temperature']}°{period['temperatureUnit']}
                Wind: {period['windSpeed']} {period['windDirection']}
                Forecast: {period['detailedForecast']}
                """
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

# Run the server
if __name__ == "__main__":
    # Support specifying transport via CLI, e.g. python server.py stdio or python server.py sse
    transport = "sse"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower().replace("--", "")
        if arg in ("stdio", "sse"):
            transport = arg

    if transport == "stdio":
        # Do not print to stdout in stdio mode as stdout is reserved for JSON-RPC messages
        mcp.run(transport="stdio")
    elif transport == "sse":
        print("Running Weather MCP server with SSE transport on http://localhost:8000")
        print("SSE Endpoint: http://localhost:8000/sse")
        print("Landing page: http://localhost:8000/")
        mcp.run(transport="sse")
    else:
        raise ValueError(f"Unknown transport: {transport}. Expected 'stdio' or 'sse'.")
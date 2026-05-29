from mcp.server.fastmcp import FastMCP
from browser_actions import search_google, search_youtube
from mac_actions import (
    open_app,
    open_website,
    open_folder,
    run_profile
)
from system_actions import (
    get_battery_status,
    get_current_time,
    get_disk_space,
    get_cpu_usage,
    lock_mac
)

mcp = FastMCP("mac-jarvis")


@mcp.tool()
def jarvis_open_app(app_name: str) -> str:
    """Open an app on macOS."""
    return open_app(app_name)


@mcp.tool()
def jarvis_open_website(site_or_url: str) -> str:
    """Open a website."""
    return open_website(site_or_url)


@mcp.tool()
def jarvis_open_folder(path: str) -> str:
    """Open folder in Finder."""
    return open_folder(path)


@mcp.tool()
def jarvis_run_profile(profile_name: str) -> str:
    """Run app workflow profile."""
    return run_profile(profile_name)

@mcp.tool()
async def jarvis_search_google(query: str) -> str:
    """Search Google using browser automation."""
    return await search_google(query)


@mcp.tool()
async def jarvis_search_youtube(query: str) -> str:
    """Search YouTube using browser automation."""
    return await search_youtube(query)

@mcp.tool()
def jarvis_battery_status() -> str:
    """Get Mac battery status."""
    return get_battery_status()


@mcp.tool()
def jarvis_current_time() -> str:
    """Get current time."""
    return get_current_time()


@mcp.tool()
def jarvis_disk_space() -> str:
    """Get available disk space."""
    return get_disk_space()


@mcp.tool()
def jarvis_cpu_usage() -> str:
    """Get CPU usage."""
    return get_cpu_usage()


@mcp.tool()
def jarvis_lock_mac() -> str:
    """Lock or sleep Mac display."""
    return lock_mac()

if __name__ == "__main__":
    mcp.run()
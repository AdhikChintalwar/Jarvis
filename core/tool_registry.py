TOOL_REGISTRY = {
    "open_app": {
        "mcp_tool": "jarvis_open_app",
        "arg_name": "app_name",
        "spoken": "Opening",
        "remember": True
    },
    "open_website": {
        "mcp_tool": "jarvis_open_website",
        "arg_name": "site_or_url",
        "spoken": "Opening",
        "remember": True
    },
    "open_folder": {
        "mcp_tool": "jarvis_open_folder",
        "arg_name": "path",
        "spoken": "Opening folder",
        "remember": True
    },
    "run_profile": {
        "mcp_tool": "jarvis_run_profile",
        "arg_name": "profile_name",
        "spoken": "Starting profile",
        "remember": True
    },
    "open_project": {
        "mcp_tool": "jarvis_open_project",
        "arg_name": "project_name",
        "spoken": "Opening project",
        "remember": False
    },
    "search_google": {
        "mcp_tool": "jarvis_search_google",
        "arg_name": "query",
        "spoken": "Searching Google for",
        "remember": False
    },
    "search_youtube": {
        "mcp_tool": "jarvis_search_youtube",
        "arg_name": "query",
        "spoken": "Searching YouTube for",
        "remember": False
    },
    "battery_status": {
    "mcp_tool": "jarvis_battery_status",
    "arg_name": None,
    "spoken": None,
    "remember": False,
    "speak_result": True
},
"current_time": {
    "mcp_tool": "jarvis_current_time",
    "arg_name": None,
    "spoken": None,
    "remember": False,
    "speak_result": True
},
"disk_space": {
    "mcp_tool": "jarvis_disk_space",
    "arg_name": None,
    "spoken": None,
    "remember": False,
    "speak_result": True
},
"cpu_usage": {
    "mcp_tool": "jarvis_cpu_usage",
    "arg_name": None,
    "spoken": None,
    "remember": False,
    "speak_result": True
},
"lock_mac": {
    "mcp_tool": "jarvis_lock_mac",
    "arg_name": None,
    "spoken": "Locking your Mac",
    "remember": False,
    "speak_result": False
},
"take_screenshot": {
    "mcp_tool": "jarvis_take_screenshot",
    "arg_name": None,
    "spoken": "Taking screenshot",
    "remember": False,
    "speak_result": True
},
"take_and_open_screenshot": {
    "mcp_tool": "jarvis_take_and_open_screenshot",
    "arg_name": None,
    "spoken": "Taking and opening screenshot",
    "remember": False,
    "speak_result": True
},
"analyze_screen": {
    "mcp_tool": "jarvis_analyze_screen",
    "arg_name": None,
    "spoken": "Analyzing screen",
    "remember": False,
    "speak_result": True
},
"analyze_screen_vision": {
    "mcp_tool": "jarvis_analyze_screen_vision",
    "arg_name": None,
    "spoken": "Analyzing screen vision",
    "remember": False,
    "speak_result": True
},
"get_youtube_video_details": {
    "mcp_tool": "jarvis_get_youtube_video_details",
    "arg_name": "query",
    "spoken": "Getting YouTube video details for",
    "remember": False,
    "speak_result": True
},
"get_youtube_titles": {
    "mcp_tool": "jarvis_get_youtube_titles",
    "arg_name": "query",
    "spoken": "Getting YouTube titles for",
    "remember": False,
    "speak_result": True
}
}

def get_registered_tool(action: str):
    return TOOL_REGISTRY.get(action)

def get_tool_descriptions() -> str:
    """
    Return a formatted list of available tools for the LLM.
    """

    lines = []

    for name, info in TOOL_REGISTRY.items():
        desc = info.get("description", "No description")
        category = info.get("category", "general")

        lines.append(
            f"- {name} ({category}): {desc}"
        )

    return "\n".join(lines)
"""Gemini Live function declarations exposed by Nexus Core."""

TOOL_DECLARATIONS = [
    {
        "name": "undo",
        "description": (
            "Roll back the last change made to the computer — reversing a file move, "
            "copy, create, or edit, a desktop organization, a volume or brightness change, "
            "or a Wi-Fi toggle. Call this whenever the user says undo, revert, take it back, "
            "put it back, restore, or says they made a mistake. "
            "Use action='list' when they ask what can be undone."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "undo (default) — reverse the last change | list — show what can be undone",
                },
            },
        },
    },
    {
        "name": "recall_memory",
        "description": (
            "Search long-term memory for stored facts, preferences, user info, projects, or history. "
            "Use this when the user asks 'do you remember', 'what is my...', or when context about "
            "past instructions or preferences is needed."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Keyword or topic to search for in memory (e.g. 'project', 'coffee', 'birthday', 'preference')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "execute_protocol",
        "description": (
            "Activates or switches high-level macro system directives (protocols) across the PC. "
            "Call this whenever the user asks to activate, engage, start, run, or switch to a protocol: "
            "'deep_work' (deep focus mode), 'redline' (gaming / max power performance), "
            "'lockdown' (instant lock and security mute), or 'nightfall' (evening standby wrap-up)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "protocol": {
                    "type": "STRING",
                    "description": "Name of the protocol: 'deep_work', 'redline', 'lockdown', 'nightfall'",
                },
            },
            "required": ["protocol"],
        },
    },
    {
        "name": "get_sensorium_telemetry",
        "description": (
            "Read real-time situational awareness telemetry: current active application, "
            "window title, task dwell time in seconds, user idle time, CPU/RAM load, and battery health."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "manage_local_model",
        "description": (
            "Inspect, download, or switch offline local LLM models on the machine. "
            "action='status' returns available models and server health. "
            "action='pull' downloads a new model (e.g., 'qwen2.5:3b', 'llama3.2:3b'). "
            "action='toggle_offline' switches between local offline inference and cloud."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "One of: 'status', 'pull', 'toggle_offline', 'set_active'",
                },
                "model_name": {
                    "type": "STRING",
                    "description": "Model name when pulling or setting active (e.g. 'qwen2.5:3b', 'llama3.2:3b')",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "dev_agent",
        "description": (
            "An autonomous coding agent that builds full projects, writes code, installs dependencies, "
            "runs the project, and automatically fixes errors. Use this when the user asks you to 'write a script', "
            "'build an app', 'code a program', or 'run a project'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {
                    "type": "STRING",
                    "description": "A very detailed description of what the project should do."
                },
                "language": {
                    "type": "STRING",
                    "description": "The programming language to use (e.g., 'python', 'javascript')"
                },
                "project_name": {
                    "type": "STRING",
                    "description": "A short, snake_case name for the project folder."
                }
            },
            "required": ["description"]
        }
    },
    {
        "name": "background_monitor",
        "description": (
            "Sets up a background monitor to check crypto prices, system RAM/CPU, or website uptime. "
            "Use this when the user asks to be alerted when a condition is met (e.g., 'tell me if RAM goes over 90%' or 'alert me if bitcoin drops below 50000')."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "'add' to create a monitor (default), 'list' to see active monitors."
                },
                "type": {
                    "type": "STRING",
                    "description": "One of: 'system', 'crypto', 'website'"
                },
                "target": {
                    "type": "STRING",
                    "description": "What to monitor (e.g. 'ram', 'cpu', 'bitcoin', 'https://example.com')"
                },
                "threshold": {
                    "type": "NUMBER",
                    "description": "The threshold value (e.g. 90 for 90%, 50000 for $50k)"
                },
                "condition": {
                    "type": "STRING",
                    "description": "'above' or 'below'"
                },
                "interval": {
                    "type": "INTEGER",
                    "description": "How often to check in seconds (default 60)"
                }
            },
            "required": []
        }
    },
    {
        "name": "system_manager",
        "description": (
            "Checks the system health (CPU, RAM, disk, battery) and lists top resource-hogging apps. "
            "Can also be used to forcefully close or kill frozen or heavy applications."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "What to do: 'status' to check system health (default), or 'kill' to close an app."
                },
                "process_name": {
                    "type": "STRING",
                    "description": "The exact name of the process to kill (if action is 'kill'), e.g. 'chrome.exe' or 'Spotify'"
                },
                "pid": {
                    "type": "INTEGER",
                    "description": "The PID of the process to kill (if action is 'kill')"
                }
            },
            "required": []
        }
    },
    {
        "name": "check_instagram_messages",
        "description": (
            "Checks your Instagram inbox for any recent unread or direct messages. "
            "Use this when the user asks 'do I have any messages', 'check my instagram', or similar."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "clipboard_processor",
        "description": (
            "Instantly reads the current text copied to the user's Windows clipboard. "
            "Use this whenever the user asks you to read, analyze, or fix what they just copied to their clipboard."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "instagram_reply",
        "description": "Replies to a pending Instagram message or takes over the Instagram chat in auto-mode.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Must be 'take_over' to handle it automatically, or 'manual_reply' to send a specific text message."
                },
                "reply_text": {
                    "type": "STRING",
                    "description": "The exact message to send to the user if action is 'manual_reply'."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "instagram_send_dm",
        "description": "Sends an Instagram direct message to a username or conversation thread, and automatically opens the chat in your browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient": {
                    "type": "STRING",
                    "description": "The Instagram username (e.g. 'john_doe') or numeric thread ID."
                },
                "message": {
                    "type": "STRING",
                    "description": "The message text to send."
                },
                "open_in_browser": {
                    "type": "BOOLEAN",
                    "description": "Whether to auto-open the chat thread in your browser (default: true)."
                }
            },
            "required": ["recipient", "message"]
        }
    },
    {
        "name": "instagram_post_photo",
        "description": "Publishes a photo directly to your Instagram feed and automatically opens the live post in your browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {
                    "type": "STRING",
                    "description": "Absolute path to the JPG or PNG image file to publish."
                },
                "caption": {
                    "type": "STRING",
                    "description": "The caption text with optional hashtags for the post."
                },
                "open_in_browser": {
                    "type": "BOOLEAN",
                    "description": "Whether to auto-open the published post in your browser (default: true)."
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "instagram_post_reel",
        "description": "Publishes a video or Reel directly to your Instagram account and automatically opens the live Reel in your browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "video_path": {
                    "type": "STRING",
                    "description": "Absolute path to the MP4 video file to publish."
                },
                "caption": {
                    "type": "STRING",
                    "description": "The caption text with optional hashtags."
                },
                "thumbnail_path": {
                    "type": "STRING",
                    "description": "Optional path to cover image."
                },
                "open_in_browser": {
                    "type": "BOOLEAN",
                    "description": "Whether to auto-open the published Reel in your browser (default: true)."
                }
            },
            "required": ["video_path"]
        }
    },
    {
        "name": "instagram_get_user_info",
        "description": "Looks up profile details, bio, follower count, following count, and verified badge for any Instagram handle.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "username": {
                    "type": "STRING",
                    "description": "The Instagram username to look up (e.g. 'natgeo' or 'openai')."
                }
            },
            "required": ["username"]
        }
    },
    {
        "name": "open_app",
        "description": (
            "Opens any application on the Windows computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": (
            "Fetches live real-time weather, forecast, and temperature for any city or location. "
            "Call this whenever the user asks about the weather, temperature, rain, or forecast for any city or location."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, Instagram DMs, or other messaging platform. Can also upload media to Instagram when mode=upload and media_path is supplied.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name for DMs"},
                "message_text": {"type": "STRING", "description": "The message to send or Instagram caption"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, Instagram, etc."},
                "mode":         {"type": "STRING", "description": "dm | upload (Instagram only; default: dm)"},
                "media_path":   {"type": "STRING", "description": "Optional image/video path for Instagram uploads"}
            },
            "required": ["platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Windows Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."},
                "confirmed":   {"type": "STRING", "description": "Pass 'yes' if the user explicitly confirmed a dangerous action like 'shutdown' or 'restart'."}
            },
            "required": []
        }
    },
    {
        "name": "smart_home_control",
        "description": (
            "Controls connected smart-home devices such as Atomberg fans and TP-Link Kasa lights/plugs. "
            "Use when the user asks to turn devices on or off, set fan speed, change brightness, or control a room."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Natural language smart-home command"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "connect_list_devices",
        "description": (
            "Lists devices connected to Nexus Connect. Use when the user asks what devices are connected, "
            "what is online, or wants a simple inventory of paired devices."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "connect_get_device",
        "description": (
            "Gets the details for one connected device by name, id, or natural reference such as my phone, "
            "my laptop, my PC, or my tablet."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device": {"type": "STRING", "description": "Device name, id, or natural reference"},
                "target": {"type": "STRING", "description": "Alias for device"},
                "device_id": {"type": "STRING", "description": "Exact device id"},
                "name": {"type": "STRING", "description": "Exact device name"},
                "query": {"type": "STRING", "description": "Search query"},
            },
            "required": ["device"]
        }
    },
    {
        "name": "connect_get_capabilities",
        "description": (
            "Returns the capabilities and permissions reported by a connected device. "
            "Use before trying any device command."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device": {"type": "STRING", "description": "Device name, id, or natural reference"},
                "target": {"type": "STRING", "description": "Alias for device"},
                "device_id": {"type": "STRING", "description": "Exact device id"},
                "name": {"type": "STRING", "description": "Exact device name"},
                "query": {"type": "STRING", "description": "Search query"},
            },
            "required": ["device"]
        }
    },
    {
        "name": "connect_execute",
        "description": (
            "Routes a Nexus Connect command to a paired device through the gateway. "
            "Use for actions such as launch_app, open_url, get_battery, capture_screen, take_photo, "
            "clipboard_get, clipboard_set, send_file, receive_file, media_play, media_pause, volume_set, "
            "notification_list, get_device_info, close_app, mouse_move, keyboard_type, unlock_phone, file_list, file_read, file_write, file_delete."
            "Do not execute device operations directly anywhere else."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device": {"type": "STRING", "description": "Target device name, id, or natural reference"},
                "target": {"type": "STRING", "description": "Alias for device"},
                "device_id": {"type": "STRING", "description": "Exact device id"},
                "name": {"type": "STRING", "description": "Exact device name"},
                "query": {"type": "STRING", "description": "Search query"},
                "action": {"type": "STRING", "description": "Command to execute on the device"},
                "parameters": {"type": "OBJECT", "description": "Action parameters"},
            },
            "required": ["device", "action"]
        }
    },
    {
        "name": "unlock_device",
        "description": "Unlocks a paired Android device using its saved PIN.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {"type": "STRING", "description": "Device name or ID to unlock"}
            },
            "required": ["target"]
        }
    },
    {
        "name": "connect_pair_device",
        "description": (
            "Creates or approves Nexus Connect pairing. Use to generate a QR code / pairing code for a new device, "
            "or to approve a pending pairing request."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device_name": {"type": "STRING", "description": "Optional device name shown in the pairing flow"},
                "platform": {"type": "STRING", "description": "android | windows | ios | tablet | other"},
                "pending_id": {"type": "STRING", "description": "Pending request id to approve"},
            },
            "required": []
        }
    },
    {
        "name": "connect_disconnect_device",
        "description": (
            "Disconnects a device from Nexus Connect and marks it offline. "
            "Use when the user asks to disconnect, log out, or stop a paired device."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device": {"type": "STRING", "description": "Target device name, id, or natural reference"},
                "target": {"type": "STRING", "description": "Alias for device"},
                "device_id": {"type": "STRING", "description": "Exact device id"},
                "name": {"type": "STRING", "description": "Exact device name"},
                "query": {"type": "STRING", "description": "Search query"},
                "reason": {"type": "STRING", "description": "Optional reason for disconnect"},
            },
            "required": ["device"]
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Complete browser automation powered by Microsoft Playwright MCP. "
            "Use for: opening websites, web searching, navigating, semantic accessibility snapshots, "
            "clicking elements or snapshot references, typing, form filling, hovering, executing JavaScript, "
            "taking screenshots, managing tabs, and any web-based task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | navigate | search | click | hover | type | scroll | fill_form | snapshot | find | evaluate | screenshot | press | back | forward | refresh | open_tab | new_tab | switch_tab | list_tabs | wait_for | select_option | upload | console | network | close"},
                "url":         {"type": "STRING", "description": "URL for go_to/navigate"},
                "query":       {"type": "STRING", "description": "Search query or search term for find"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type/hover"},
                "element":     {"type": "STRING", "description": "Snapshot element reference (e.g. e2)"},
                "text":        {"type": "STRING", "description": "Text to click, type, or wait for"},
                "description": {"type": "STRING", "description": "Element description for smart targeting"},
                "direction":   {"type": "STRING", "description": "up or down for scroll"},
                "key":         {"type": "STRING", "description": "Key name for press action (Enter, Tab, Escape, etc.)"},
                "expression":  {"type": "STRING", "description": "JavaScript expression to evaluate in page"},
                "path":        {"type": "STRING", "description": "File path for screenshot or upload"},
                "tab":         {"type": "INTEGER", "description": "1-based tab index for switch_tab"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": (
            "Manages files and folders: open, close, list, create, delete, move, copy, rename, read, write, find, disk usage, "
            "and organizing a desktop or any folder into subfolders by type/date. Can also be used to explore and manage files on a connected Android phone."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "open | close | list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | organize_folder | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home. For android, use paths like downloads, documents, photos, movies, root."},
                "target":      {"type": "STRING", "description": "If operating on an Android device, provide the device name or ID. Leave empty for PC local files."},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
                "mode":        {"type": "STRING", "description": "by_type or by_date for organize actions"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "smart_organizer",
        "description": (
            "Smart Desktop & Downloads Organizer MCP with safe transaction rollback (undo), "
            "dry-run previews, duplicate file detection, empty folder cleanup, and archiving. "
            "Use when the user asks to organize, preview, declutter, clean, or find duplicate files on the desktop, downloads, or any folder."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "preview | organize | undo | find_duplicates | clean_empty_folders | archive_old"},
                "target": {"type": "STRING", "description": "Target folder: 'desktop' | 'downloads' | 'documents' | 'pictures' or a custom directory path"},
                "mode":   {"type": "STRING", "description": "by_type (categorizes into Documents, Images/Screenshots, Installers, Code, Archives, etc.) or by_date (YYYY-MM)"},
                "days":   {"type": "INTEGER", "description": "Number of days for archive_old (default: 30)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, preview, clean, undo, find_duplicates, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | preview | clean | undo | find_duplicates | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "file_processor",
        "description": (
            "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
            "text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
            "ALWAYS call this tool when a non-Word file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx via word_document; txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
        }
    },
    {
        "name": "presentation_builder",
        "description": (
            "Creates editable PowerPoint presentations (.pptx) from a structured slide outline. "
            "Nexus Core automatically infers the best visual style from the topic, searches for a matching online template when available, "
            "reuses cached templates, and falls back to the built-in designer if no suitable template is found. "
            "Use when the user asks for a deck, slideshow, presentation, pitch deck, or report slides."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Presentation title"},
                "subtitle": {"type": "STRING", "description": "Optional subtitle or audience line"},
                "theme": {
                    "type": "STRING",
                    "description": "Optional presentation theme or visual direction such as neon, corporate, luxury, academic, sunset, or creative. If omitted, Nexus Core infers the best style automatically."
                },
                "outline": {
                    "type": "STRING",
                    "description": "Slide-by-slide outline. Use blank lines to separate slides if slides array is omitted."
                },
                "slides": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING", "description": "Slide title"},
                            "kicker": {"type": "STRING", "description": "Short all-caps kicker"},
                            "bullets": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Bullet points for the slide"
                            },
                            "notes": {"type": "STRING", "description": "Optional speaker note or footnote"}
                        },
                        "required": ["title"]
                    },
                    "description": "Structured slides. Preferred when the model can format the deck directly."
                },
                "output_path": {"type": "STRING", "description": "Optional output path for the .pptx"},
                "auto_open": {"type": "BOOLEAN", "description": "Open the file after creating it (default: true)"},
            },
            "required": ["title"]
        }
    },
    {
        "name": "spreadsheet_builder",
        "description": (
            "Creates editable Excel workbooks (.xlsx) from structured sheet data. "
            "Use for trackers, tables, analysis workbooks, budgets, planners, and other spreadsheet requests."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Workbook title"},
                "worksheets": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING", "description": "Worksheet name"},
                            "title": {"type": "STRING", "description": "Optional sheet title row"},
                            "headers": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Column headers"
                            },
                            "rows": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "ARRAY",
                                    "items": {"type": "STRING"},
                                },
                                "description": "Data rows"
                            },
                            "chart": {
                                "type": "OBJECT",
                                "properties": {
                                    "type": {"type": "STRING", "description": "bar | line | pie"},
                                    "title": {"type": "STRING", "description": "Chart title"},
                                    "anchor": {"type": "STRING", "description": "Cell anchor such as E2"},
                                    "x_axis": {"type": "STRING", "description": "Optional x-axis title"},
                                    "y_axis": {"type": "STRING", "description": "Optional y-axis title"},
                                }
                            }
                        },
                        "required": ["name"]
                    },
                    "description": "One or more worksheets to create."
                },
                "output_path": {"type": "STRING", "description": "Optional output path for the .xlsx"},
                "auto_open": {"type": "BOOLEAN", "description": "Open the file after creating it (default: true)"},
            },
            "required": ["title"]
        }
    },
    {
        "name": "word_document",
        "description": (
            "Creates, edits, reads, summarizes, extracts text from, and opens editable Word documents (.docx). "
            "Use for Word document requests, letters, reports, headings, bullets, formatting edits, and preserving existing formatting."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "create | create_letter | create_report | read | summarize | extract_text | append | replace_text | add_heading | add_bullets | reformat | open"
                },
                "file_path": {"type": "STRING", "description": "Existing .docx file path for read/edit/open actions"},
                "output_path": {"type": "STRING", "description": "Optional output path for the saved .docx"},
                "title": {"type": "STRING", "description": "Document title"},
                "doc_type": {"type": "STRING", "description": "letter | report | generic"},
                "content": {"type": "STRING", "description": "Main body content or text to append"},
                "body": {"type": "STRING", "description": "Body text for letter/report creation"},
                "paragraphs": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Paragraphs to add"},
                "bullets": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Bullet items to add"},
                "numbered": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Numbered items to add"},
                "sections": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Structured sections with heading/body/bullets"},
                "replacements": {"type": "OBJECT", "description": "Find/replace mapping for formatting-preserving edits"},
                "find": {"type": "STRING", "description": "Text to find for simple replace_text edits"},
                "replace": {"type": "STRING", "description": "Replacement text for simple replace_text edits"},
                "heading": {"type": "STRING", "description": "Heading text to append"},
                "level": {"type": "INTEGER", "description": "Heading level 1-3"},
                "recipient": {"type": "STRING", "description": "Letter recipient"},
                "salutation": {"type": "STRING", "description": "Custom letter salutation"},
                "closing": {"type": "STRING", "description": "Custom letter closing"},
                "date": {"type": "STRING", "description": "Letter date"},
                "author": {"type": "STRING", "description": "Document author"},
                "subject": {"type": "STRING", "description": "Document subject"},
                "open_after": {"type": "BOOLEAN", "description": "Open the saved document after writing (default: true)"},
                "save": {"type": "BOOLEAN", "description": "Save large generated summaries to a text file"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "pdf_document",
        "description": (
            "Creates editable-style PDF documents (.pdf) from structured content or converts DOCX / text files into PDFs. "
            "Use for PDF creation, PDF exports, and PDF generation requests that need a direct file output."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "create | create_report | create_letter | convert"
                },
                "file_path": {"type": "STRING", "description": "Existing file to convert, typically .docx or .txt"},
                "output_path": {"type": "STRING", "description": "Optional output path for the saved .pdf"},
                "title": {"type": "STRING", "description": "PDF title"},
                "subtitle": {"type": "STRING", "description": "Optional subtitle"},
                "content": {"type": "STRING", "description": "Main body content"},
                "body": {"type": "STRING", "description": "Main body content"},
                "paragraphs": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Paragraphs to add"},
                "bullets": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Bullet items to add"},
                "numbered": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Numbered items to add"},
                "sections": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Structured sections with heading/body/bullets"},
                "recipient": {"type": "STRING", "description": "Letter recipient"},
                "salutation": {"type": "STRING", "description": "Custom letter salutation"},
                "closing": {"type": "STRING", "description": "Custom letter closing"},
                "date": {"type": "STRING", "description": "Letter date"},
                "author": {"type": "STRING", "description": "Document author"},
                "subject": {"type": "STRING", "description": "Document subject"},
                "auto_open": {"type": "BOOLEAN", "description": "Open the file after creating it (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "shutdown_nexus",
        "description": (
            "Shuts down the assistant completely. "
        "Call this when the user expresses intent to end the conversation, "
        "close the assistant, say goodbye, or stop Nexus Core. "
        "The user can say this in ANY language."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. User, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "spotify_controller",
        "description": (
            "Plays and controls music via Spotify, Spotify MCP, and Google Chrome. "
            "ALWAYS use this tool whenever the user asks to play any song, music, track, or artist "
            "(e.g. 'play Starboy', 'play music on Spotify'), or control playback "
            "('pause the music', 'resume', 'skip song', 'next track', 'volume up', 'volume down', 'mute'). "
            "Do NOT use open_app for playing songs."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "search_play | play | pause | toggle | next | previous | volume_up | volume_down | set_volume | get_now_playing | get_playlists | get_queue | get_devices | auth | mute | open_spotify (default: search_play)"
                },
                "query": {
                    "type": "STRING",
                    "description": "Song title, artist name, album, or playlist to search and play"
                },
                "volume": {
                    "type": "NUMBER",
                    "description": "Volume level (optional)"
                },
                "device_id": {
                    "type": "STRING",
                    "description": "Optional Spotify Connect playback device ID"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "calendar_scheduler",
        "description": (
            "Manages calendar events, appointments, and schedules. "
            "Use whenever the user asks to schedule a meeting, check upcoming events, "
            "view schedule for today/tomorrow, or remove an event."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "add_event | list_events | check_day | delete_event | get_upcoming | export_ics"
                },
                "title": {
                    "type": "STRING",
                    "description": "Title or summary of the meeting/event"
                },
                "date": {
                    "type": "STRING",
                    "description": "Date (YYYY-MM-DD or 'today', 'tomorrow')"
                },
                "time": {
                    "type": "STRING",
                    "description": "Time (HH:MM in 24h format, e.g. '14:30')"
                },
                "duration_minutes": {
                    "type": "NUMBER",
                    "description": "Duration in minutes (default: 30)"
                },
                "location": {
                    "type": "STRING",
                    "description": "Location or meeting link (optional)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "daily_briefing",
        "description": (
            "Delivers a complete daily briefing including time, date, today's schedule/calendar events, "
            "and top world & tech headlines. Use whenever the user asks for their daily briefing, morning update, "
            "or what's happening today."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "Optional news category: all (default), tech, world"
                }
            },
            "required": []
        }
    },
    {
        "name": "google_workspace",
        "description": (
            "Full Google Workspace MCP for Gmail, Calendar, and Google Drive automation. "
            "Supports: reading unread emails, listing inbox, searching emails, sending emails; "
            "listing calendar events, adding calendar events; "
            "searching Drive files, reading Drive files, and uploading files to Google Drive."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "gmail | calendar | drive"
                },
                "action": {
                    "type": "STRING",
                    "description": "gmail actions: 'list', 'unread', 'read', 'search', 'send' | calendar actions: 'list', 'add' | drive actions: 'list', 'search', 'read', 'upload'"
                },
                "to": {
                    "type": "STRING",
                    "description": "Recipient email address for sending emails"
                },
                "subject": {
                    "type": "STRING",
                    "description": "Subject for sending or searching emails"
                },
                "body": {
                    "type": "STRING",
                    "description": "Body message for email"
                },
                "query": {
                    "type": "STRING",
                    "description": "Search query for Gmail or Drive"
                },
                "email_id": {
                    "type": "STRING",
                    "description": "ID of email to read"
                },
                "title": {
                    "type": "STRING",
                    "description": "Title/summary for calendar event"
                },
                "date": {
                    "type": "STRING",
                    "description": "Date for calendar event (YYYY-MM-DD or today/tomorrow)"
                },
                "time": {
                    "type": "STRING",
                    "description": "Time for calendar event (HH:MM)"
                },
                "duration_minutes": {
                    "type": "NUMBER",
                    "description": "Duration in minutes"
                },
                "file_path": {
                    "type": "STRING",
                    "description": "Local file path or name for Drive upload/read"
                }
            },
            "required": ["service", "action"]
        }
    },
    {
        "name": "system_diagnostics",
        "description": (
            "Local OS Hardware and System Diagnostics MCP. "
            "Checks battery health, power status, CPU usage and thermals, RAM utilization and top memory/CPU hogs, "
            "storage drive space, and controls multi-monitor display brightness. Can safely terminate frozen apps."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "status | ram_hogs | cpu_hogs | kill | brightness | battery | disk"
                },
                "target": {
                    "type": "STRING",
                    "description": "Application name (e.g. 'chrome', 'notepad') or numerical PID to terminate"
                },
                "level": {
                    "type": "NUMBER",
                    "description": "Display brightness level from 0 to 100"
                },
                "monitor": {
                    "type": "STRING",
                    "description": "Optional target monitor name or index"
                },
                "relative": {
                    "type": "BOOLEAN",
                    "description": "Whether brightness level is relative (+10, -10)"
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maximum number of processes to return (default: 5)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "auto_heal",
        "description": (
            "Autonomous Self-Healing and Continuous Self-Improvement System. "
            "Analyzes tracebacks/exceptions in first-party codebase, synthesizes surgical code hotfixes, "
            "validates AST syntax in safety sandbox, applies hotfixes with atomic backup, or rolls back changes. "
            "Also manages learned behavioral rules and persistent user directives."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "status | heal | history | rollback | learn_rule | list_rules"
                },
                "error_traceback": {
                    "type": "STRING",
                    "description": "The exact exception traceback or error message to heal"
                },
                "rule_text": {
                    "type": "STRING",
                    "description": "The user preference, habit, or behavioral directive to remember permanently"
                },
                "category": {
                    "type": "STRING",
                    "description": "Category for learned rule (general, formatting, workflow, habit)"
                },
                "patch_id": {
                    "type": "STRING",
                    "description": "Specific patch ID to rollback (default: latest)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "circuit_assembler",
        "description": "Designs a safe electronic wiring schematic from component names or a screen image, then shows the interactive circuit HUD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "assemble_components | analyze_screen | show_schematic"},
                "components": {"type": "STRING", "description": "Electronic components, such as Arduino Uno, ESP32, DHT11, or HC-SR04."},
                "query": {"type": "STRING", "description": "Circuit goal or wiring question."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "geospatial_globe",
        "description": "Opens Nexus Core's interactive 3D map for routes, live aircraft, weather, earthquakes, nearby places, and ISS tracking.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open | route | drive | location | fly_to | weather | flights | iss | earthquakes | nearby | radar | inspect"},
                "origin": {"type": "STRING", "description": "Origin city for a route."},
                "destination": {"type": "STRING", "description": "Destination city for a route."},
                "location": {"type": "STRING", "description": "City or area to focus on."},
                "query": {"type": "STRING", "description": "Nearby place category, such as hospitals, fuel, or restaurants."},
                "min_magnitude": {"type": "NUMBER", "description": "Minimum earthquake magnitude to display."},
                "enable": {"type": "BOOLEAN", "description": "Enable or disable the weather radar overlay."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "call_screening",
        "description": "Screens an incoming call with Nexus Core as an AI attendant. Answering always waits for the user to confirm on the Echo HUD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start | take_over | hang_up"},
                "caller": {"type": "STRING", "description": "Caller name or notification title."},
                "app": {"type": "STRING", "description": "Calling application, such as Phone Link, WhatsApp, or Teams."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "skill_forge",
        "description": "Use whenever the user explicitly asks to make, create, build, or add a new skill or feature. Starts creation immediately, validates the generated Python feature, and registers it for use. Do not use screen analysis for feature-creation requests.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "forge | list"},
                "goal": {"type": "STRING", "description": "What new capability the skill should provide."},
                "skill_name": {"type": "STRING", "description": "Optional short name for the skill."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "dynamic_skill",
        "description": "Lists and runs installed Nexus Core skills, including stock, crypto, cricket, speed-test, and ISS examples. Running a skill requires user confirmation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | run"},
                "skill_name": {"type": "STRING", "description": "Skill name to run."},
                "arguments": {"type": "OBJECT", "description": "Arguments for the selected skill."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "calorie_counter",
        "description": (
            "Analyzes food and meals to report calories, macronutrients (protein, carbs, fat, fiber), "
            "and dietary advice. Can capture a live snapshot via webcam, inspect an image file, "
            "or analyze a spoken/typed meal description. "
            "Use whenever the user asks about the calories or nutritional value of food."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Food or meal description (e.g. 'How many calories in this plate?', 'I had 2 eggs and toast')."
                },
                "image_path": {
                    "type": "STRING",
                    "description": "Optional local file path to a food photo."
                },
                "use_camera": {
                    "type": "BOOLEAN",
                    "description": "True to capture a live photo from the webcam."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "pushup_counter",
        "description": (
            "Live AI workout and repetition counter. Tracks reps, tempo, and calories burned "
            "for pushups, squats, and bodyweight exercises through the webcam with live HUD overlay. "
            "Use whenever the user asks to count pushups, track squats, or start a workout."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "User's request (e.g. 'count my pushups', 'track 20 squats')."
                },
                "exercise": {
                    "type": "STRING",
                    "description": "pushups | squats | general"
                },
                "target": {
                    "type": "INTEGER",
                    "description": "Target rep goal (e.g. 20)."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "upload_video",
        "description": (
            "Automates video publishing to TikTok, YouTube Shorts, or Instagram. "
            "Auto-locates recent videos on Desktop/Downloads, generates viral SEO captions and tags, "
            "copies metadata to clipboard, reveals the file in Explorer, and launches the studio uploader."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {
                    "type": "STRING",
                    "description": "Video topic, caption brief, or context (in user's language)."
                },
                "platform": {
                    "type": "STRING",
                    "description": "tiktok | youtube | instagram (default: tiktok)"
                },
                "video_path": {
                    "type": "STRING",
                    "description": "Optional path to the video file to publish."
                }
            },
            "required": ["description"]
        }
    },
    {
        "name": "reverse_engineer",
        "description": (
            "Reverse engineer any website, desktop application, or native binary without source code. "
            "Extracts API surfaces, network schemas, client bundles, or native pseudocode, "
            "and can automatically remake/replicate a clean working version in your project. "
            "Supports web URLs (https://...), desktop apps (.exe, Electron .asar), and .wasm."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {
                    "type": "STRING",
                    "description": "Target website URL (e.g. 'https://example.com') or local file/folder path (e.g. 'C:/Apps/target.exe' or 'D:/electron-app')"
                },
                "action": {
                    "type": "STRING",
                    "description": "'analyze' (architectural breakdown), 'remake' (generate a working clone project), 'api_surface' (extract backend API schemas only), 'decompile' (pseudocode of native binary or JS bundle)"
                },
                "feature": {
                    "type": "STRING",
                    "description": "Specific feature, component, or behavior to investigate (e.g. 'search modal', 'auth flow', 'database query')"
                },
                "destination": {
                    "type": "STRING",
                    "description": "Optional local folder to write the remade code, assets, or extracted schemas into"
                }
            },
            "required": ["target"]
        }
    },
    {
        "name": "generate_image",
        "description": (
            "Generates stunning AI images, concept art, photorealistic photos, and 3D renders from text prompts. "
            "Saves the high-resolution image to Desktop, shows a preview on the HUD, and opens it automatically. "
            "Use whenever the user asks to generate, create, draw, paint, or visualize an image or picture."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {
                    "type": "STRING",
                    "description": "Detailed text description of the image to generate."
                },
                "style": {
                    "type": "STRING",
                    "description": "Style: 'photorealistic', 'cyberpunk', 'anime', 'cinematic_3d', 'digital_art', 'concept_art', 'fantasy', or 'minimalist' (default: photorealistic)."
                },
                "aspect_ratio": {
                    "type": "STRING",
                    "description": "Aspect ratio: '1:1' (square), '16:9' (landscape), '9:16' (portrait) (default: 1:1)."
                },
                "destination": {
                    "type": "STRING",
                    "description": "Optional custom folder path to save the generated image."
                }
            },
            "required": ["prompt"]
        }
    },
    # =========================================================================
    # UNIVERSAL CLAUDE-CODE & OPENAI CODEX TOOL SUITE (PROJECT OMNIPOTENCE)
    # =========================================================================
    {
        "name": "bash",
        "description": "Execute a shell or PowerShell command on the local machine with captured output, timeouts, and smart truncation. Essential for compilers, package managers (npm, pip, cargo), git, and running scripts.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "The exact shell or PowerShell command to execute"},
                "timeout": {"type": "INTEGER", "description": "Timeout in seconds (default 120)"},
                "cwd": {"type": "STRING", "description": "Optional working directory path"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "file_read",
        "description": "Read file contents with line numbers starting at offset up to limit lines. Line numbers help target surgical file_edit updates.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Relative or absolute path to the file"},
                "offset": {"type": "INTEGER", "description": "Line number to start reading from (1-based, default 1)"},
                "limit": {"type": "INTEGER", "description": "Maximum number of lines to read (default 2000)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "file_edit",
        "description": "Surgically edit an existing file by replacing old_string with new_string. Whitespace, indentation, and newlines must match exactly. Fails safely if old_string is not found or ambiguous.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path to the file to edit"},
                "old_string": {"type": "STRING", "description": "Exact text block to replace, including exact indentation"},
                "new_string": {"type": "STRING", "description": "Replacement text block"},
                "replace_all": {"type": "BOOLEAN", "description": "Whether to replace every occurrence (default false)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["file_path", "old_string", "new_string"]
        }
    },
    {
        "name": "file_write",
        "description": "Write or overwrite a file with full content. Automatically creates any missing parent directories.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path to the file to write"},
                "content": {"type": "STRING", "description": "Complete text content of the file"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "glob",
        "description": "Fast recursive file search by pattern (e.g. '**/*.py', 'src/**/*.tsx', '*.json'). Automatically skips .git, node_modules, .venv, dist.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Glob pattern to match"},
                "path": {"type": "STRING", "description": "Subdirectory to search inside (default '.')"},
                "max_results": {"type": "INTEGER", "description": "Maximum number of files to return (default 100)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "grep",
        "description": "Fast regex and keyword search across file contents with line numbers and file paths. Essential for finding symbols, functions, and errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Regex pattern or literal text to search for"},
                "path": {"type": "STRING", "description": "Subdirectory to search inside (default '.')"},
                "case_sensitive": {"type": "BOOLEAN", "description": "Case sensitive matching (default true)"},
                "max_results": {"type": "INTEGER", "description": "Maximum number of matches (default 50)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "python_repl",
        "description": "Execute Python code in an isolated computational sandbox (Codex / Advanced Data Analysis). Use for math calculations, data analysis with pandas/numpy, and generating charts/plots with matplotlib.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "code": {"type": "STRING", "description": "Valid Python code to execute"},
                "timeout": {"type": "INTEGER", "description": "Execution timeout in seconds (default 60)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "git_manager",
        "description": "Autonomous Git version control operations: status, diff, log, commit, branch, checkout, add, push, pull.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Git action: 'status', 'diff', 'diff_staged', 'log', 'commit', 'branch', 'checkout', 'new_branch', 'push', 'pull'"},
                "message": {"type": "STRING", "description": "Commit message (required for 'commit')"},
                "branch": {"type": "STRING", "description": "Branch name (for 'branch', 'checkout', 'new_branch')"},
                "cwd": {"type": "STRING", "description": "Optional repository path"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "test_and_heal",
        "description": "Run automated test suites (pytest, npm test, cargo test) and analyze failure stack traces to verify code functionality.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Test command to execute (default 'pytest')"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            }
        }
    },
    {
        "name": "subagent_task",
        "description": "Spawn an autonomous child subagent (researcher, coder, tester) to perform parallel background tasks without cluttering the primary conversation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "role": {"type": "STRING", "description": "Role: 'researcher' (code survey/read-only), 'coder' (build/execution), 'tester' (test verification)"},
                "prompt": {"type": "STRING", "description": "Specific task instructions for the subagent"},
                "workspace": {"type": "STRING", "description": "Optional workspace directory path"},
                "wait": {"type": "BOOLEAN", "description": "Whether to wait for completion (default true)"}
            },
            "required": ["role", "prompt"]
        }
    },
    {
        "name": "mcp_status",
        "description": "Check the connection status and discovered tools of all configured MCP servers (Model Context Protocol).",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "skill_execute",
        "description": "Execute or consult an installed community or markdown skill (e.g. 'code-review', 'test-driven-development', 'git-workflow', 'database-architect', 'docker-devops', 'web-scraper-stealth'). Returns the comprehensive guidelines, directives, and protocols for the skill.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "skill_name": {"type": "STRING", "description": "Name of the skill to execute/consult"},
                "task": {"type": "STRING", "description": "Specific user task or question to apply the skill to"}
            },
            "required": ["skill_name"]
        }
    },
    {
        "name": "skill_install",
        "description": "Install a new markdown skill into Nexus Core's skills/ library, allowing Nexus Core to perpetually learn new procedures and protocols from the internet or user.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "skill_name": {"type": "STRING", "description": "Short slug name for the skill (e.g. 'pdf-analyzer')"},
                "content": {"type": "STRING", "description": "Full Markdown/YAML SKILL.md definition"}
            },
            "required": ["skill_name", "content"]
        }
    },
    {
        "name": "skill_list",
        "description": "List all installed community and markdown skills available in Nexus Core.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "todo_write",
        "description": "Claude Code style task list tracker. Update the active multi-step plan checklist with status for each task (pending, in_progress, completed).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "todos": {
                    "type": "ARRAY",
                    "description": "List of task objects: [{'id': '1', 'task': '...', 'status': 'pending'|'in_progress'|'completed'}]",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING"},
                            "task": {"type": "STRING"},
                            "status": {"type": "STRING"}
                        },
                        "required": ["id", "task", "status"]
                    }
                }
            },
            "required": ["todos"]
        }
    },
    {
        "name": "todo_read",
        "description": "Read the active task checklist and current step progress.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },

]

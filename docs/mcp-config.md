# MCP Configuration Examples

`time-tui` exposes its Markdown-backed store as MCP tools over stdio. Any
MCP-capable client (Claude Desktop, custom agents, inspector) can launch
the server as a subprocess.

## stdio transport (recommended)

```json
{
  "mcpServers": {
    "time-tui": {
      "command": "todo-mcp",
      "args": ["--root", "/home/kutay/Documents/GitHub/time-tui"],
      "env": {}
    }
  }
}
```

`command` should resolve to the installed entry point. If not on `PATH`,
point it at the venv binary:

```json
{
  "mcpServers": {
    "time-tui": {
      "command": "/home/kutay/Documents/GitHub/time-tui/.venv/bin/todo-mcp",
      "args": ["--root", "/home/kutay/Documents/GitHub/time-tui"]
    }
  }
}
```

`TIME_TUI_ROOT` env var works too if you prefer the server to discover the
root itself:

```json
{
  "mcpServers": {
    "time-tui": {
      "command": "todo-mcp",
      "env": { "TIME_TUI_ROOT": "/home/kutay/Documents/GitHub/time-tui" }
    }
  }
}
```

## Tools exposed

| Tool | Purpose |
|---|---|
| `task_list` | List tasks in a namespace |
| `task_add` | Add a top-level task |
| `task_add_child` | Add a child task under a parent |
| `task_done` | Mark a task as done |
| `task_rename` | Rename a task |
| `task_delete` | Delete a task (and descendants with `cascade=True`) |
| `task_move` | Move a task to a different namespace |
| `calendar_today` | List today's events |
| `calendar_list` | List events on a date |
| `calendar_add` | Add a single event |
| `calendar_add_bulk` | Add multiple events on a date |
| `calendar_delete` | Delete an event |
| `calendar_move` | Move an event's start time |
| `session_today` | List today's sessions |
| `session_log` | List sessions on a date |
| `session_add` | Log a manual session entry |
| `namespace_list` | List namespaces |
| `namespace_create` | Create a namespace |

All list-shaped returns are wrapped in a dict (`{"tasks": [...]}`,
`{"events": [...]}`, `{"sessions": [...]}`, `{"namespaces": [...]}`) so the
client receives a single structured payload per call.

## ChatGPT web (Streamable HTTP)

ChatGPT web cannot launch the local stdio command directly. Start the same
server with the optional Streamable HTTP transport instead:

```bash
/home/kutay/Documents/GitHub/time-tui/.venv/bin/todo-mcp \
  --root /home/kutay/Documents/GitHub/time-tui \
  --transport streamable-http
```

The MCP endpoint is then `http://127.0.0.1:8000/mcp`. It intentionally binds
to loopback by default, so it is not exposed to the LAN or public internet.
Connect this endpoint to ChatGPT using OpenAI Secure MCP Tunnel, then enter the
tunnel-provided HTTPS endpoint in ChatGPT under **Settings → Apps → Create**.

The port and endpoint path can be changed without affecting stdio clients:

```bash
todo-mcp --root /path/to/project --transport streamable-http \
  --port 8765 --http-path /mcp
```

Do not bind the server to `0.0.0.0` or expose it publicly without adding
authentication and HTTPS in front of it. The tools can modify task, calendar,
and session data.

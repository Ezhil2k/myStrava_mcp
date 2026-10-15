#!/usr/bin/env python3
from __future__ import annotations
import sys
from strava_tui import load_env, service_status, start_services, stop_services, tail

load_env()
command = sys.argv[1] if len(sys.argv) > 1 else "status"
if command == "start":
    print(start_services())
elif command == "stop":
    print(stop_services())
elif command == "restart":
    stop_services()
    print(start_services())
elif command == "status":
    sp, sport, tp, tread = service_status()
    print(f"MCP server: {'running' if sp and sport else 'stopped'}")
    print(f"Secure tunnel: {'running' if tp and tread else 'stopped'}")
elif command == "test":
    print("MCP endpoint reachable." if service_status()[1] else "MCP endpoint is not reachable.")
elif command == "logs":
    print("\n".join(tail("tunnel", 40)))
else:
    print(f"Unknown command: {command}", file=sys.stderr)
    raise SystemExit(2)

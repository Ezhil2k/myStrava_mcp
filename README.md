# Strava MCP — read-only, multi-profile adapter

This server exposes named Strava credential profiles through read-only MCP
tools. Each person can connect their own Strava credential locally; credentials
are never accepted as MCP tool arguments and are never included in responses.

## Run

The tested environment is:

    /tmp/strava-research/venv/bin/python /home/armistice/.ssh/strava-mcp/server.py

By default, profiles are loaded from:

    /home/armistice/.ssh/strava-mcp/profiles/<profile>.json

Set STRAVA_CREDENTIALS_DIR to use another directory. Each profile file must be
mode 600 and contain exactly one of these objects:

    {"access_token": "YOUR_TOKEN"}
    {"session_cookie": "YOUR_BROWSER_SESSION_COOKIE"}

For compatibility, the original STRAVA_SESSION_FILE environment variable and
the project-local session.json are still accepted for the default profile.
STRAVA_ACCESS_TOKEN or STRAVA_SESSION_COOKIE can also configure only the
default profile. Do not put a credential in chat, source control, or an MCP
tool call.

## Connect a browser profile

The helper imports only the _strava4_session cookie from a local Brave or
Chromium profile and writes a mode-600 profile file. It does not print the
cookie:

    /tmp/strava-research/venv/bin/python connect_session.py --profile alice --browser brave

Use --credentials-dir when profiles should live outside the project. Token
users can create the JSON file directly with the schema above, preferably via
an OS secret-management workflow.

## MCP tools

The server provides strava_profiles, strava_auth_status, and
strava_connect_instructions for profile discovery and setup. Data tools accept
profile="name": strava_profile, strava_activities, strava_activity,
strava_streams, strava_gear, strava_stats, strava_training, and the fixed
read-only dispatcher strava_query.

The dispatcher accepts only these kinds: profile, activities, activity,
streams, gear, stats, and training. There is no arbitrary endpoint tool.

For a shared MCP process, the process owner must protect the credentials
directory because a profile selector can access any profile configured for that
process. The safer multi-person deployment is one server process and profile
directory per user.

## Current coverage and limits

The browser-session adapter was live-tested against the authorized account:
activity history pagination and activity pages returned data, while streams,
laps, and training-log routes were denied or unavailable. API-token mode is
implemented for athlete, activity search/details, streams, gear, statistics,
and training-log reads, subject to Strava account permissions. This remains a
private, reverse-engineered adapter rather than an official Strava API client;
coverage is not guaranteed to be complete or stable.

The adapter uses only fixed GET routes, does not follow redirects, does not
retry authentication/rate-limit failures, verifies activity ownership before
returning activity details or streams, and enforces request spacing.

## Development

### HTTP transport

STDIO is still the default and is used by MCP Inspector. To run the same
server as a local HTTP MCP endpoint for a secure MCP tunnel:

Copy `.env.example` to `.env` and fill in the runtime API key. The server
loads `.env` automatically. The tunnel client is a separate process, so load
the same file into the shell before starting it.

    cp .env.example .env
    set -a; source .env; set +a
    .venv/bin/python server.py --transport streamable-http

If the tunnel profile must be initialized or re-created:

    tunnel-client init --profile strava-http \
      --tunnel-id "$STRAVA_TUNNEL_ID" \
      --mcp-server-url "http://127.0.0.1:8001/mcp"

The streamable HTTP endpoint is:

    http://127.0.0.1:8001/mcp

In another terminal, load `.env` and run the tunnel client:

    cd ~/dew/strava-mcp
    set -a; source .env; set +a
    tunnel-client run --profile strava-http --health.listen-addr "$TUNNEL_HEALTH_LISTEN_ADDR"

### Simple CLI

The `stravactl` helper manages the Strava server and tunnel together. From
this directory, run:

    chmod +x stravactl
    ./stravactl

It also supports `./stravactl start`, `stop`, `restart`, `status`, `test`, and
`logs`. It only manages Strava's server and tunnel processes; Garmin's port
8000 is not touched.

Keep it bound to `127.0.0.1` and expose it only through an authenticated,
trusted MCP tunnel. Do not bind it to `0.0.0.0` or publish it directly: the
server can read every credential profile in its configured directory.

Run tests from this directory:

    /tmp/strava-research/venv/bin/python -m unittest -v test_server.py

The implementation was informed by static analysis of the installed Strava
483.10 Android APK with Ghidra and JADX. The original research artifacts and
read-only surface audit remain alongside this project.

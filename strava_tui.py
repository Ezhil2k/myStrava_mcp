"""Fixed-screen terminal dashboard for the Strava MCP services."""
from __future__ import annotations

import curses
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / ".run"
LOG_DIR = ROOT / "logs"


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] in "'\"" and value[-1] == value[0]:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def pid_path(name: str) -> Path:
    return STATE_DIR / f"{name}.pid"


def pid(name: str) -> int | None:
    try:
        value = int(pid_path(name).read_text(encoding="utf-8").strip())
        os.kill(value, 0)
        return value
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return None


def running(name: str) -> bool:
    return pid(name) is not None


def start_one(name: str, command: list[str]) -> None:
    if running(name):
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = (LOG_DIR / f"{name}.log").open("a", encoding="utf-8")
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True, cwd=ROOT)
    pid_path(name).write_text(str(process.pid), encoding="utf-8")


def stop_one(name: str) -> None:
    value = pid(name)
    if value is None:
        pid_path(name).unlink(missing_ok=True)
        return
    try:
        os.kill(value, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            try:
                os.kill(value, 0)
            except ProcessLookupError:
                break
        else:
            os.kill(value, signal.SIGKILL)
    except ProcessLookupError:
        pass
    pid_path(name).unlink(missing_ok=True)


def start_services() -> str:
    python = os.environ.get("STRAVA_PYTHON", str(ROOT / ".venv" / "bin" / "python"))
    profile = os.environ.get("STRAVA_TUNNEL_PROFILE", "strava-http")
    health = os.environ.get("TUNNEL_HEALTH_LISTEN_ADDR", "127.0.0.1:8081")
    client = os.environ.get("TUNNEL_CLIENT", "tunnel-client")
    start_one("server", [python, str(ROOT / "server.py")])
    start_one("tunnel", [client, "run", "--profile", profile,
                          "--health.listen-addr", health])
    return "Services started in the background."


def stop_services() -> str:
    stop_one("tunnel")
    stop_one("server")
    return "Services stopped."


def port_open(host: str, port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def health_ready() -> bool:
    host, port = os.environ.get("TUNNEL_HEALTH_LISTEN_ADDR", "127.0.0.1:8081").rsplit(":", 1)
    try:
        with urllib.request.urlopen(f"http://{host}:{int(port)}/readyz", timeout=1) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def service_status() -> tuple[bool, bool, bool, bool]:
    host = os.environ.get("STRAVA_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("STRAVA_MCP_PORT", "8001"))
    return running("server"), port_open(host, port), running("tunnel"), health_ready()


def tail(name: str, lines: int = 8) -> list[str]:
    try:
        content = (LOG_DIR / f"{name}.log").read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return []
    return content.splitlines()[-lines:]


def tunnel_connected() -> bool:
    text = "\n".join(tail("tunnel", 40)).lower()
    return any(word in text for word in ("forwarded command", "poll", "started"))


def add(screen: curses.window, row: int, col: int, text: str, attr: int = 0) -> None:
    if 0 <= row < curses.LINES and col < curses.COLS:
        try:
            screen.addnstr(row, col, text, max(1, curses.COLS - col - 1), attr)
        except curses.error:
            pass


def strava_banner() -> list[str]:
    glyphs = {
        "S": ("11111", "10000", "01110", "11110"),
        "T": ("11111", "00100", "00100", "00100"),
        "R": ("11110", "10001", "11110", "10100"),
        "A": ("01110", "10001", "11111", "10001"),
        "V": ("10001", "10001", "01010", "00100"),
        "M": ("10001", "11011", "10101", "10001"),
        "C": ("01111", "10000", "10000", "01111"),
        "P": ("11110", "10001", "11110", "10000"),
    }
    rows = []
    for row in range(4):
        rendered = []
        for letter in "STRAVA MCP":
            if letter == " ":
                rendered.append("  ")
                continue
            rendered.append("".join(
                "█" if bit == "1" else " "
                for bit in glyphs[letter][row]
            ))
        rows.append("  ".join(rendered))
    return rows


def dashboard_main() -> int:
    load_env()
    message = start_services()

    def draw(screen: curses.window) -> None:
        nonlocal message
        curses.curs_set(1)
        screen.timeout(80)
        screen.keypad(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)
            if curses.COLORS >= 256:
                curses.init_pair(5, 208, -1)
            else:
                curses.init_pair(5, curses.COLOR_YELLOW, -1)
        buffer = ""
        show_lines = 100
        title = strava_banner()
        while True:
            screen.erase()
            server_proc, server_port, tunnel_proc, tunnel_ready = service_status()
            for index, line in enumerate(title):
                add(screen, index, 2, line, curses.color_pair(5) | curses.A_BOLD)
            server_color = curses.color_pair(1) if server_port else curses.color_pair(2)
            tunnel_color = curses.color_pair(1) if tunnel_ready or (tunnel_proc and tunnel_connected()) else curses.color_pair(2)
            add(screen, 6, 2, "MCP server     ", curses.A_BOLD)
            add(screen, 6, 17, f"{'RUNNING' if server_proc else 'STOPPED':8}  ", curses.A_BOLD)
            add(screen, 6, 27, "●", server_color)
            add(screen, 7, 2, "Secure tunnel  ", curses.A_BOLD)
            add(screen, 7, 17, f"{'RUNNING' if tunnel_proc else 'STOPPED':8}  ", curses.A_BOLD)
            add(screen, 7, 27, "●", tunnel_color)
            row = 9
            width = max(10, curses.COLS - 4)
            add(screen, row, 2, "┌─ Recent tunnel log " + "─" * max(1, width - 21) + "┐", curses.color_pair(4) | curses.A_BOLD)
            available = max(1, curses.LINES - row - 7)
            lines = tail("tunnel", min(show_lines, available)) or ["No tunnel log yet."]
            for line in lines:
                row += 1
                add(screen, row, 2, "│ ", curses.color_pair(4))
                add(screen, row, 4, line, curses.A_DIM)
            add(screen, row + 1, 2, "└" + "─" * max(1, width - 2) + "┘", curses.color_pair(4) | curses.A_BOLD)
            prompt_row = max(row + 3, curses.LINES - 3)
            add(screen, prompt_row - 2, 2, "Commands:  [r] start   [x] stop   [s] status   [t] test   [l] logs   [q] quit", curses.color_pair(4) | curses.A_BOLD)
            add(screen, prompt_row - 1, 2, f"Response:  {message}", curses.color_pair(3))
            add(screen, prompt_row, 2, "Command: ", curses.A_BOLD)
            add(screen, prompt_row, 11, buffer)
            screen.refresh()
            key = screen.getch()
            if key in (10, 13):
                command = buffer.strip().lower()
                buffer = ""
                if command in {"q", "quit", "exit"}:
                    return
                if command in {"r", "run", "start"}:
                    message = start_services()
                elif command in {"x", "stop"}:
                    message = stop_services()
                elif command in {"s", "status"}:
                    message = "Status refreshed."
                elif command in {"t", "test"}:
                    message = "MCP endpoint reachable." if service_status()[1] else "MCP endpoint is not reachable."
                elif command in {"l", "logs"}:
                    show_lines = 8 if show_lines > 8 else 100
                    message = f"Showing {show_lines} recent tunnel log lines."
                elif command:
                    message = "Unknown command. Use: r, x, s, t, l, q."
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                buffer = buffer[:-1]
            elif 32 <= key <= 126:
                buffer += chr(key)

    curses.wrapper(draw)
    return 0


if __name__ == "__main__":
    raise SystemExit(dashboard_main())

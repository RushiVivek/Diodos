# Diodos

`diodos` is a CLI daemon that monitors your network and automatically attempts login when a captive portal is detected.

[View diodos on PyPI](https://pypi.org/project/diodos/)

## Features

- Checks connectivity on a configurable interval.
- Detects likely captive-portal redirects.
- Submits configured credentials automatically.
- Works with `python -m diodos` and the installed `diodos` command.
- Runs on Windows, macOS and Linux.

## Installation

### With uv (recommended)

Install as a global CLI tool:

```bash
uv tool install diodos
```

Run without installing globally:

```bash
uvx diodos start
```

### With pip (alternative)

```bash
pip install diodos
```

### From source

```bash
git clone <your-repo-url>
cd Diodos
uv sync
```

## Upgrade

For an existing uv installation:

```bash
uv tool install -U diodos
```

For an existing pip installation:

```bash
python -m pip install --upgrade diodos
```

To run the latest published version without installing it permanently:

```bash
uvx --refresh diodos start
```

## Usage

The installed `diodos` command is the recommended way to use the CLI. The available commands are:

Launch the daemon in the background:

```bash
diodos start
```

Run the daemon process in the foreground:

```bash
diodos daemon
```

Check for a captive portal and attempt a one-time login:

```bash
diodos login
```

Log out from the captive portal:

```bash
diodos logout
```

Open the configuration file:

```bash
diodos config
```

Stop a running background daemon:

```bash
diodos stop
```

You can also run any command with `uvx` without installing the package globally. For example:

```bash
uvx diodos logout
```

Or run the CLI as a Python module:

```bash
python -m diodos start
```

On first run, `diodos` creates a default config file and opens it for editing.

## Configuration

Default config path:

- Linux: `~/.config/diodos/config.toml` (or `$XDG_CONFIG_HOME/diodos/config.toml`)
- macOS: `~/Library/Application Support/diodos/config.toml`
- Windows: `%APPDATA%/diodos/config.toml`

Set `DIODOS_CONFIG_DIR` to keep the config, cookie jar and PID file somewhere
else. The file may be saved as UTF-8 with or without a byte order mark.

Example:

```toml
[network]
SSID = "Example SSID"

[network_check]
url = "https://example.com"
msg = "Success"
interval = 60

[login]
url = "https://portal.example.com/login"

[login.credentials]
username = "your-username"
password = "your-password"

[logout]
url = "https://portal.example.com/logout"
```

## Platform notes

### Windows

`diodos start` launches the daemon detached, so it keeps running after the
terminal that started it is closed and no console window appears. Use
`diodos stop` to shut it down. The current SSID is read with `netsh wlan show
interfaces`.

`.toml` has no associated program on a default Windows install, so the first
`diodos config` opens Windows' own "How do you want to open this file?" picker.
Choose an editor there, and tick the box to remember it. Setting `EDITOR` (or
`VISUAL`) bypasses the picker and overrides the choice on every platform.

### macOS and Linux

The SSID is read with `networksetup` on macOS and `nmcli` on Linux. If neither
is available the SSID check is skipped and connectivity alone decides whether
to log in.

## Development

Build distributables:

```bash
uv build
```

Validate package metadata:

```bash
uvx twine check dist/*
```

Run the cross-platform smoke test, which exercises config discovery, the
cookie jar and daemon control against a local stand-in portal:

```bash
python tests/smoke_test.py
```

# Diodos

`diodos` is a CLI daemon that monitors your network and automatically attempts login when a captive portal is detected.

[View diodos on PyPI](https://pypi.org/project/diodos/)

## Features

- Checks connectivity on a configurable interval.
- Detects captive portals the way Android and ChromeOS do, with a `generate_204` probe.
- Picks the right portal from the Wi-Fi name, so one config covers college, home and so on, with several SSIDs per portal.
- Submits the login form, then confirms the internet actually works.
- Works with `python -m diodos` and the installed `diodos` command.
- Runs on Windows, macOS, Linux and Android (Termux).

> **Tested on:** diodos is only fully tested on an Arch Linux machine. Windows,
> macOS and Android support is covered by CI smoke tests but not used day to
> day, so please [open an issue](https://github.com/RushiVivek/Diodos/issues)
> for any bug you find on another OS.

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

- Android (Termux): `~/.config/diodos/config.toml`

Set `DIODOS_CONFIG_DIR` to keep the config, cookie jar and PID file somewhere
else. The file may be saved as UTF-8 with or without a byte order mark.

`diodos config` creates a commented sample that explains every field. In short:

```toml
interval = 60  # optional: seconds between checks

[check]  # optional: this url is the default
url = "http://connectivitycheck.gstatic.com/generate_204"

# Required: one [[networks]] block per portal.
[[networks]]
name = "College"  # optional label
ssids = ["College-Hostel", "College-Library"]  # optional; [] or omitted = any network

[networks.login]  # required
url = "http://portal.example.edu:8090/login"

[networks.login.form]  # optional, but most portals need it: every field the portal's login form sends
username = "your-username"
password = "your-password"

[networks.logout]  # optional; add a [networks.logout.form] to POST instead of GET
url = "http://portal.example.edu:8090/logout"

[[networks]]
name = "Home"
ssids = ["Home-WiFi"]

[networks.login]
url = "http://192.168.1.1/login"

[networks.login.form]
username = "your-username"
password = "your-password"
```

When the internet is unreachable, diodos reads the current Wi-Fi name and logs
in through the network that lists it. If the name cannot be read, it only uses
a network with `ssids = []`. A network that lists SSIDs never has its
credentials sent anywhere else.

A running daemon re-reads the config on every check, so edits apply without a
restart. Config files from before 0.5 (`[network]`, `[network_check]`,
`[login.credentials]`) still work unchanged.

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

The SSID is read with `networksetup` on macOS, and with `nmcli` or `iwgetid`
on Linux.

> **macOS:** on recent macOS (15 Sequoia and later), `networksetup -getairportnetwork` reports
> "You are not associated with an AirPort network" even while connected,
> because Apple hides the Wi-Fi name from command-line tools that lack the
> location permission. diodos then cannot tell which network you are on, so it
> only logs in through a network with `ssids = []`. On a Mac, use that setup.

### Android (Termux)

Install [Termux](https://termux.dev) from F-Droid or GitHub (the Play Store
build is outdated), then:

```bash
pkg install python
pip install diodos
```

To pick a network by Wi-Fi name, diodos needs the
[Termux:API](https://wiki.termux.com/wiki/Termux:API) app plus
`pkg install termux-api`, and the Termux:API app needs the location permission
with location turned on. Android hides the Wi-Fi name from apps without it.
Without Termux:API, use `ssids = []`.

Android suspends background apps, so keep the daemon alive with:

```bash
termux-wake-lock
diodos start
```

To start it at boot, install Termux:Boot and put those two lines in an
executable script in `~/.termux/boot/`. As an alternative to the daemon, an
automation app that can run Termux commands (for example through
Termux:Tasker) can run `diodos login` whenever Wi-Fi connects.

If Android shows "connected, no internet" and switches to mobile data, the
check succeeds over mobile data and diodos sees nothing to do. Turn off
mobile data, or Android's "switch to mobile data" option, while on the portal
network.

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

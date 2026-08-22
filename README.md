# diodos

`diodos` is a CLI daemon that monitors your network and automatically attempts login when a captive portal is detected.

## Features

- Checks connectivity on a configurable interval.
- Detects likely captive-portal redirects.
- Submits configured credentials automatically.
- Works with `python -m diodos` and the installed `diodos` command.

## Installation

### With uv (recommended)

Install as a global CLI tool:

```bash
uv tool install diodos
```

Run without installing globally:

```bash
uvx diodos run
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

## Usage

```bash
diodos run
```

Or:

```bash
python -m diodos run
```

On first run, `diodos` creates a default config file and opens it for editing.

## Configuration

Default config path:

- Linux: `~/.config/diodos/config.toml` (or `$XDG_CONFIG_HOME/diodos/config.toml`)
- macOS: `~/Library/Application Support/diodos/config.toml`
- Windows: `%APPDATA%/diodos/config.toml`

Example:

```toml
[network_check]
url = "https://example.com"
msg = "Success"
interval = 60

[login]
url = "https://portal.example.com/login"

[login.credentials]
username = "your-username"
password = "your-password"
```

## Development

Build distributables:

```bash
uv build
```

Validate package metadata:

```bash
uvx twine check dist/*
```

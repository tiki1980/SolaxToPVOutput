# SolaxToPVOutput

Poll SolaxCloud and upload the latest inverter data to PVOutput.

PVOutput API: <https://pvoutput.org/help.html#api-addstatus>  
SolaxCloud API: <https://www.solaxcloud.com/#/api>

## Setup

1. Create and activate a virtual environment.
2. Install the project in editable mode:

```bash
pip install -e .[dev]
```

3. Copy `config.example.yml` to one of these locations:

- `%APPDATA%\\SolaxToPVOutput\\config.yml` on Windows
- `~/.config/solaxtopvoutput/config.yml` on Linux and macOS
- `./config.yml` in the repo as a local fallback

4. Fill in your real values or provide the secrets through environment
   variables.
5. Run a single sync for validation:

```bash
solaxtopvoutput --once
```

6. Run the long-lived polling process:

```bash
solaxtopvoutput
```

You can always override the config path explicitly:

```bash
solaxtopvoutput --config path/to/config.yml
```

The app checks config files in this order:

1. `SOLAXTOPVOUTPUT_CONFIG` if set
2. the per-user config file
3. `./config.yml`

## Configuration

```yaml
SolaxToPVOutput:
  logLevel: "WARNING"
  pollIntervalSeconds: 300
  logFile: "solaxtopvoutput.log"

SolaxCloud:
  apiUrl: "https://global.solaxcloud.com"
  tokenId: "your-solax-token"
  registrationNr: "your-wifi-registration-number"

PVOutput:
  systemid: 123456
  apikey: "your-pvoutput-api-key"

SunWindow:
  enabled: false
  latitude: 52.1326
  longitude: 5.2913
  timezone: "Europe/Amsterdam"
  startEvent: "sunrise"
  endEvent: "sunset"
```

Relative `logFile` paths are resolved relative to the selected config file.

## Sun Window

Issue #3 requested limiting checks to solar-active hours. When `SunWindow`
is enabled, the app only polls between the configured start and end solar
markers using `astral`.

Supported events:

- `startEvent`: `dawn` or `sunrise`
- `endEvent`: `sunset` or `dusk`

Outside the active window, the app skips API calls and sleeps until the next
window opens.

## Runtime Behavior

Successful polls run at the configured interval. Repeated failures back off
progressively up to 5x the configured interval, then return to the normal
cadence after a successful sync.

## Environment Overrides

These environment variables override YAML values when set:

- `SOLAXTOPVOUTPUT_CONFIG`
- `SOLAXTOPVOUTPUT_LOG_LEVEL`
- `SOLAXTOPVOUTPUT_POLL_INTERVAL_SECONDS`
- `SOLAXTOPVOUTPUT_LOG_FILE`
- `SOLAXCLOUD_API_URL`
- `SOLAXCLOUD_TOKEN_ID`
- `SOLAXCLOUD_REGISTRATION_NR`
- `PVOUTPUT_SYSTEM_ID`
- `PVOUTPUT_API_KEY`

For normal operation, keep non-secret defaults in YAML and provide secrets
through environment variables.

## Linux Notes

On Linux the default user config path is:

```bash
~/.config/solaxtopvoutput/config.yml
```

The long-running process now handles `SIGTERM` cleanly, so it behaves well
under `systemd`, Docker, and other service managers.

Typical Linux setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
solaxtopvoutput --once
```

## Development

Run formatting, linting, and tests with:

```bash
black src tests
ruff check src tests
pytest
```

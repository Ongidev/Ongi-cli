# ongi-cli

Private anime streaming CLI with dub/sub support, multi-provider fallback, AES-256-CTR source decryption, and a GUI episode navigator.

## Arguments

| Flag | Description |
|------|-------------|
| `-d`, `--dub` | Stream dubbed version (English) |
| `-s`, `--sub` | Stream subbed version (default) |
| `--default d\|s` | Save dub/sub as the permanent default |
| `-t`, `--test` | Test all API endpoints |
| `-H`, `--history` | Show last 20 watched episodes |
| `--instmissingdep` | Auto-install missing dependencies |
| `--alias <name>` | Create a shell alias (e.g. `--alias ani`) |
| `-h`, `--help` | Show help message |

## Usage

```bash
ongi-cli                      # Interactive search prompt
ongi-cli "one piece"          # Search sub
ongi-cli -d "naruto"          # Search dub
ongi-cli -d jjk               # No quotes needed for single words
ongi-cli --default d          # Save dub as default forever
ongi-cli --test               # Test APIs
ongi-cli --instmissingdep     # Install mpv, fzf, pycryptodome if missing
ongi-cli --alias ani          # Create 'ani' as a shortcut
```

## Navigation flow

```
Search prompt
  └─ Type anime name → results list (fzf or numbered)
       └─ Select anime → episode list (fzf or numbered)
            └─ Select episode → mpv plays
                 └─ Close mpv → popup navigator appears
                      ├─ Next / Prev / Replay → plays next episode
                      ├─ Episode list → back to episode picker
                      └─ Quit → back to Search prompt
```

**Escape / 0 at any selection screen → back to Search prompt.**  
**Ctrl+C → exit.**

## Playback popup controls

After mpv closes a GUI popup appears. Click a button or press the key while the popup is focused:

| Key / Button | Action |
|--------------|--------|
| `n` | Next episode |
| `p` | Previous episode |
| `r` | Replay current episode |
| `s` | Back to episode list |
| `q` / Esc | Back to search bar |

> Prev/Next buttons are automatically greyed out at the start/end of a series.

## Features

- **Persistent search loop** — `q` always returns to the search bar, never exits
- **Sub & Dub** — switch with `-d` / `-s`; save default with `--default`
- **Multi-provider fallback** — tries Yt-mp4 → Default → Vid-mp4 → Ok → Fm-Hls → Ss-Hls → S-mp4 → Ak → Luf-Mp4
- **AES-256-CTR decryption** — handles AllAnime's encrypted `tobeparsed` responses
- **GUI episode navigator** — tkinter popup avoids terminal pty issues after mpv
- **fzf selection** — fuzzy search through results (falls back to numbered list)
- **Watch history** — tracks every episode watched (`--history` to view)
- **API testing** — verify all endpoints are alive (`--test`)
- **Auto-install** — detects scoop / choco / winget / brew / apt / pacman

## Requirements

- **Python 3.10+**
- **mpv** — video player
- **pycryptodome** — AES decryption (`pip install pycryptodome`)
- **fzf** — fuzzy finder (optional, falls back to numbered list)
- **tkinter** — included with standard Python on Windows

## Install

```bash
# Install missing dependencies automatically
ongi-cli --instmissingdep

# Or manually:
pip install pycryptodome
scoop install mpv fzf    # Windows (scoop)
```

### Add to PATH (scoop shims)

```bash
cp ongi-cli.py ~/scoop/shims/ongi-cli.py

cat > ~/scoop/shims/ongi-cli << 'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -u "$SCRIPT_DIR/ongi-cli.py" "$@"
EOF
chmod +x ~/scoop/shims/ongi-cli
```

Or use `--alias` to do this automatically:

```bash
ongi-cli --alias ani   # creates both shim files
```

## How it works

1. Searches AllAnime GraphQL API for the anime
2. Fetches episode source list via persisted query
3. Decrypts AES-256-CTR encrypted `tobeparsed` fields
4. Resolves stream URLs (direct HTTP or via `clock.json`)
5. Launches mpv with the correct `Referer` header
6. After mpv exits, shows a tkinter popup for navigation

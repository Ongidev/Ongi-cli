# ongi-cli
A ani-cli distro for better compatibility on windows

Private anime streaming CLI with dub/sub support, multi-provider fallback, and encrypted source decryption.

## Arguments

| Flag | Description |
|------|-------------|
| `-d`, `--dub` | Stream dubbed version (English) |
| `-s`, `--sub` | Stream subbed version (default) |
| `-t`, `--test` | Test all API endpoints |
| `-H`, `--history` | Show watch history |
| `--instmissingdep` | Install missing dependencies |
| `--alias <name>` | Create a shell alias for ongi-cli |
| `-h`, `--help` | Show this help message |

### Playback Controls

| Key | Action |
|-----|--------|
| `n` | Next episode |
| `p` | Previous episode |
| `r` | Replay |
| `s` | Select episode |
| `q` | Quit |

## Examples

```bash
ongi-cli "one piece"          # Search sub
ongi-cli -d "naruto"          # Search dub
ongi-cli -d jjk               # Search dub (no quotes needed)
ongi-cli --test               # Test APIs
ongi-cli --instmissingdep     # Install mpv, fzf, pycryptodome if missing
ongi-cli --alias ani          # Create 'ani' as shortcut
```

## Features

- **Sub & Dub** — switch with `-d` / `-s`
- **Multi-provider fallback** — tries Yt-mp4, Default, Vid-mp4, Ok, Fm-Hls, Ss-Hls, S-mp4, Ak, Luf-Mp4 in order
- **AES-256-CTR decryption** — handles AllAnime's encrypted `tobeparsed` responses
- **fzf selection** — fuzzy search through results (falls back to numbered list)
- **Watch history** — tracks what you've watched
- **API testing** — verify all endpoints are alive

## Requirements

- **Python 3.10+**
- **mpv** — video player
- **fzf** — fuzzy finder (optional, falls back to numbered list)
- **pycryptodome** — AES decryption (`pip install pycryptodome`)

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
# Create bash launcher:
cat > ~/scoop/shims/ongi-cli << 'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/ongi-cli.py" "$@"
EOF
```

## How It Works

1. Searches AllAnime API via GraphQL
2. Fetches episode sources using persisted queries
3. Decrypts AES-256-CTR encrypted responses
4. Resolves stream URLs (direct or via clock.json)
5. Plays in mpv with proper referrer headers

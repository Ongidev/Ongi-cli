#!/usr/bin/env python3
"""
ongi-cli - Private anime streaming CLI
Complete rework with dub support, multi-provider fallback, and API testing
Requires: python3, mpv, fzf (optional), pycryptodome (pip install pycryptodome)
"""

import sys, os, json, re, subprocess, hashlib, base64, time, socket
import urllib.parse, urllib.request, urllib.error, ssl
from pathlib import Path

# Global socket timeout so DNS/SSL can't hang forever
socket.setdefaulttimeout(15)

# Fix Windows console encoding
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

VERSION = "1.0.0"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ALLANIME_API = "https://api.allanime.day"
ALLANIME_REFR = "https://allmanga.to"
ALLANIME_ORIGIN = "https://youtu-chan.com"
ALLANIME_KEY = b"Xot36i3lK3:v1"
EPISODE_HASH = "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"

AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"
PLAYER = "mpv"
PLAYER_ARGS = ["--force-window=immediate", "--no-terminal"]
HISTORY_FILE = Path.home() / ".local" / "share" / "ongi-cli" / "history.json"

# Provider priority (first working source wins)
PROVIDER_PRIORITY = ["Yt-mp4", "Default", "Vid-mp4", "Ok", "Fm-Hls", "Ss-Hls", "S-mp4", "Ak", "Luf-Mp4"]

# SSL context
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COLORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class C:
    RED = "\033[1;31m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[1;34m"
    CYAN = "\033[1;36m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def msg(text): print(f"{C.BLUE}[*]{C.RESET} {text}")
def err(text): print(f"{C.RED}[!]{C.RESET} {text}", file=sys.stderr)
def warn(text): print(f"{C.YELLOW}[~]{C.RESET} {text}")
def success(text): print(f"{C.GREEN}[✓]{C.RESET} {text}")
def die(text): err(text); sys.exit(1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CRYPTO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def decrypt_tobeparsed(encrypted_b64):
    """Decrypt allanime tobeparsed response using AES-256-CTR"""
    from Crypto.Cipher import AES
    key = hashlib.sha256(ALLANIME_KEY).digest()
    raw = base64.b64decode(encrypted_b64)
    iv_bytes = raw[1:13]
    counter = iv_bytes + bytes.fromhex("00000002")
    cipher = AES.new(key, AES.MODE_CTR, nonce=b'', initial_value=counter)
    decrypted = cipher.decrypt(raw[13:])
    text = decrypted.decode('utf-8', errors='replace')
    decoder = json.JSONDecoder()
    parsed, _ = decoder.raw_decode(text)
    return parsed

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HTTP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def http_get(url, headers=None, timeout=10):
    hdrs = {"User-Agent": AGENT}
    if headers: hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    resp = urllib.request.urlopen(req, timeout=timeout, context=CTX)
    return resp.read()

def http_post_json(url, data, headers=None, timeout=10):
    hdrs = {"User-Agent": AGENT, "Content-Type": "application/json"}
    if headers: hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=hdrs)
    resp = urllib.request.urlopen(req, timeout=timeout, context=CTX)
    return json.loads(resp.read())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ALLANIME API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEARCH_GQL = ('query( $search: SearchInput $limit: Int $page: Int '
    '$translationType: VaildTranslationTypeEnumType '
    '$countryOrigin: VaildCountryOriginEnumType ) '
    '{ shows( search: $search limit: $limit page: $page '
    'translationType: $translationType countryOrigin: $countryOrigin ) '
    '{ edges { _id name availableEpisodes __typename } }}')

EPISODES_GQL = 'query ($showId: String!) { show( _id: $showId ) { availableEpisodesDetail }}'

def search_anime(query, mode="sub"):
    """Search anime. mode: 'sub' or 'dub'"""
    data = {
        "variables": {
            "search": {"allowAdult": False, "allowUnknown": False, "query": query},
            "limit": 40, "page": 1,
            "translationType": mode,
            "countryOrigin": "ALL"
        },
        "query": SEARCH_GQL
    }
    result = http_post_json(f"{ALLANIME_API}/api", data, {"Referer": ALLANIME_REFR})
    return result.get("data", {}).get("shows", {}).get("edges", [])

def get_episode_list(show_id):
    """Get available episodes"""
    data = {"variables": {"showId": show_id}, "query": EPISODES_GQL}
    result = http_post_json(f"{ALLANIME_API}/api", data, {"Referer": ALLANIME_REFR})
    return result.get("data", {}).get("show", {}).get("availableEpisodesDetail", {})

def get_episode_sources(show_id, mode, ep_no):
    """Get episode sources via persisted query GET + tobeparsed decryption"""
    variables = {"showId": show_id, "translationType": mode, "episodeString": str(ep_no)}
    extensions = {"persistedQuery": {"version": 1, "sha256Hash": EPISODE_HASH}}
    params = urllib.parse.urlencode({
        "variables": json.dumps(variables),
        "extensions": json.dumps(extensions)
    })
    url = f"{ALLANIME_API}/api?{params}"
    raw_bytes = http_get(url, {"Origin": ALLANIME_ORIGIN, "Referer": ALLANIME_ORIGIN})
    raw = json.loads(raw_bytes)

    if "tobeparsed" in raw.get("data", {}):
        parsed = decrypt_tobeparsed(raw["data"]["tobeparsed"])
        return parsed.get("episode", {})
    return raw.get("data", {}).get("episode", {})

def resolve_source_url(source_url):
    """Resolve source URL - direct or via clock.json"""
    if source_url.startswith("http"):
        return source_url
    if source_url.startswith("--"):
        encoded = source_url[2:]
        clock_url = f"https://allanime.day/apivtwo/clock.json?id={urllib.parse.quote(encoded)}"
        try:
            resp = http_get(clock_url, {"Referer": ALLANIME_REFR}, timeout=5)
            data = json.loads(resp)
            for link in data.get("links", []):
                url = link.get("link", "")
                if url and "error" not in url.lower():
                    return url
                # Try rawUrls fallback
                raw = link.get("rawUrls", {})
                for vid in raw.get("vids", []):
                    if vid.get("url"):
                        return vid["url"]
        except Exception:
            pass
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STREAM RESOLUTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_best_stream(sources):
    """Try sources in priority order, return first working URL"""
    source_map = {s.get("sourceName", "?"): s for s in sources}

    for provider in PROVIDER_PRIORITY:
        if provider not in source_map:
            continue
        src_url = source_map[provider].get("sourceUrl", "")
        msg(f"Trying {provider}...")
        resolved = resolve_source_url(src_url)
        if resolved:
            success(f"Got stream from {provider}")
            return resolved, provider

    # Fallback: any remaining source
    tried = set(PROVIDER_PRIORITY)
    for s in sources:
        name = s.get("sourceName", "?")
        if name in tried:
            continue
        resolved = resolve_source_url(s.get("sourceUrl", ""))
        if resolved:
            success(f"Got stream from {name}")
            return resolved, name

    return None, None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PLAYBACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def play_video(url, title, episode, provider=""):
    display_title = f"{title} - Ep {episode}"
    if provider:
        display_title += f" [{provider}]"

    cmd = [PLAYER] + PLAYER_ARGS + [f"--force-media-title={display_title}"]

    if "allanime" in url or "fast4speed" in url:
        cmd.append(f"--http-header-fields=Referer: {ALLANIME_REFR}")
    elif "gogoanime" in url or "gogocdn" in url or "anihdplay" in url:
        cmd.append("--http-header-fields=Referer: https://gogoanime.film/")

    cmd.append(url)
    msg(f"Playing: {display_title}")
    msg(f"URL: {url[:80]}...")

    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        die(f"Player '{PLAYER}' not found. Install mpv.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HISTORY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_history(show_id, title, episode, mode):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if HISTORY_FILE.exists():
        try: history = json.loads(HISTORY_FILE.read_text())
        except Exception: history = []
    history.append({"timestamp": int(time.time()), "show_id": show_id,
                     "title": title, "episode": str(episode), "mode": mode})
    HISTORY_FILE.write_text(json.dumps(history[-100:], indent=2))

def show_history():
    if not HISTORY_FILE.exists():
        warn("No watch history found."); return
    history = json.loads(HISTORY_FILE.read_text())
    print(f"\n{C.CYAN}=== Watch History ==={C.RESET}\n")
    for entry in history[-20:]:
        ts = entry.get("timestamp", 0)
        date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        tag = f"[{C.GREEN}DUB{C.RESET}]" if entry.get("mode") == "dub" else f"[{C.BLUE}SUB{C.RESET}]"
        print(f"  {C.GREEN}{date_str}{C.RESET}  {tag} {entry['title']} - Ep {entry['episode']}")
    print()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def has_fzf():
    try:
        subprocess.run(["fzf", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def select_with_fzf(items, prompt="Select: ", header=""):
    cmd = ["fzf", "--prompt", prompt, "--reverse", "--cycle"]
    if header: cmd.extend(["--header", header])
    try:
        result = subprocess.run(cmd, input="\n".join(items),
                                stdout=subprocess.PIPE, stderr=None,
                                text=True, encoding="utf-8", check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        warn("fzf not found, falling back to numbered list")
        return select_with_numbers(items, prompt)

def select_with_numbers(items, prompt="Select"):
    for i, item in enumerate(items, 1):
        print(f"  {C.CYAN}{i:3d}{C.RESET}  {item}")
    print()
    while True:
        try:
            choice = input(f"{C.YELLOW}{prompt} [1-{len(items)}]: {C.RESET}").strip()
            if not choice: return None
            idx = int(choice) - 1
            if 0 <= idx < len(items): return items[idx]
            err(f"Invalid. Enter 1-{len(items)}")
        except (ValueError, EOFError):
            return None

def select_item(items, prompt="Select: ", header=""):
    if not items: return None
    if has_fzf(): return select_with_fzf(items, prompt, header)
    return select_with_numbers(items, prompt)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API TESTING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_apis():
    print(f"\n{C.CYAN}=== ongi-cli API Compatibility Test ==={C.RESET}\n")

    # Search sub
    print(f"{C.YELLOW}[1] AllAnime Search (SUB):{C.RESET}")
    try:
        r = search_anime("naruto", "sub")
        if r: print(f"  {C.GREEN}✓ WORKING{C.RESET} - {len(r)} results (e.g. {r[0]['name']})")
        else: print(f"  {C.RED}✗ FAILED{C.RESET}")
    except Exception as e: print(f"  {C.RED}✗ ERROR{C.RESET} - {e}")

    # Search dub
    print(f"\n{C.YELLOW}[2] AllAnime Search (DUB):{C.RESET}")
    try:
        r = search_anime("naruto", "dub")
        if r:
            dub_ct = r[0].get('availableEpisodes', {}).get('dub', 0)
            print(f"  {C.GREEN}✓ WORKING{C.RESET} - {len(r)} results (e.g. {r[0]['name']}, {dub_ct} dub eps)")
        else: print(f"  {C.RED}✗ FAILED{C.RESET}")
    except Exception as e: print(f"  {C.RED}✗ ERROR{C.RESET} - {e}")

    # Episode sources + decrypt
    print(f"\n{C.YELLOW}[3] Episode Sources + Decrypt:{C.RESET}")
    try:
        r = search_anime("naruto", "sub")
        if r:
            show = r[0]
            eps = get_episode_list(show['_id'])
            sub_eps = eps.get('sub', [])
            if sub_eps:
                ep = get_episode_sources(show['_id'], 'sub', sub_eps[0])
                sources = ep.get('sourceUrls', [])
                print(f"  {C.GREEN}✓ WORKING{C.RESET} - {len(sources)} sources decrypted")
                for s in sources[:5]:
                    name = s.get('sourceName', '?')
                    direct = "direct" if s.get('sourceUrl', '').startswith('http') else "encoded"
                    print(f"    {name}: {direct}")
    except Exception as e: print(f"  {C.RED}✗ ERROR{C.RESET} - {e}")

    # Stream resolution
    print(f"\n{C.YELLOW}[4] Stream URL Resolution:{C.RESET}")
    try:
        r = search_anime("naruto", "sub")
        if r:
            show = r[0]
            eps = get_episode_list(show['_id'])
            sub_eps = eps.get('sub', [])
            if sub_eps:
                ep = get_episode_sources(show['_id'], 'sub', sub_eps[0])
                sources = ep.get('sourceUrls', [])
                url, prov = get_best_stream(sources)
                if url:
                    print(f"  {C.GREEN}✓ WORKING{C.RESET} - {prov}: {url[:80]}...")
                else:
                    print(f"  {C.RED}✗ FAILED{C.RESET} - No stream resolved")
    except Exception as e: print(f"  {C.RED}✗ ERROR{C.RESET} - {e}")

    # Tools
    print(f"\n{C.YELLOW}[5] Required Tools:{C.RESET}")
    for tool in ["mpv", "fzf"]:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
            print(f"  {tool}: {C.GREEN}FOUND{C.RESET}")
        except (FileNotFoundError, subprocess.CalledProcessError):
            opt = "" if tool == "mpv" else " (optional)"
            print(f"  {tool}: {C.RED}MISSING{opt}{C.RESET}")
    print()

def install_missing():
    """Install missing dependencies"""
    print(f"\n{C.CYAN}=== ongi-cli Dependency Installer ==={C.RESET}\n")
    missing = []

    # Check pycryptodome
    try:
        from Crypto.Cipher import AES
        print(f"  pycryptodome: {C.GREEN}INSTALLED{C.RESET}")
    except ImportError:
        print(f"  pycryptodome: {C.RED}MISSING{C.RESET}")
        missing.append("pycryptodome")

    # Check mpv
    try:
        subprocess.run(["mpv", "--version"], capture_output=True, check=True)
        print(f"  mpv:          {C.GREEN}INSTALLED{C.RESET}")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"  mpv:          {C.RED}MISSING{C.RESET}")
        missing.append("mpv")

    # Check fzf
    try:
        subprocess.run(["fzf", "--version"], capture_output=True, check=True)
        print(f"  fzf:          {C.GREEN}INSTALLED{C.RESET}")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"  fzf:          {C.YELLOW}MISSING (optional){C.RESET}")
        missing.append("fzf")

    if not missing:
        print(f"\n{C.GREEN}All dependencies are installed!{C.RESET}\n")
        return

    print(f"\n{C.YELLOW}Installing missing dependencies...{C.RESET}\n")

    # Install pycryptodome via pip
    if "pycryptodome" in missing:
        msg("Installing pycryptodome via pip...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pycryptodome"],
                           check=True)
            success("pycryptodome installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            err("Failed to install pycryptodome. Try: pip install pycryptodome")

    # Detect package manager for mpv/fzf
    has_scoop = False
    has_choco = False
    has_winget = False
    has_brew = False
    has_apt = False
    has_pacman = False

    for cmd, flag in [("scoop", "has_scoop"), ("choco", "has_choco"),
                      ("winget", "has_winget"), ("brew", "has_brew"),
                      ("apt", "has_apt"), ("pacman", "has_pacman")]:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True)
            locals()[flag] = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    cli_pkgs = [p for p in missing if p in ("mpv", "fzf")]
    if not cli_pkgs:
        print()
        return

    installed_any = False
    if has_scoop:
        for pkg in cli_pkgs:
            msg(f"Installing {pkg} via scoop...")
            try:
                subprocess.run(["scoop", "install", pkg], check=True)
                success(f"{pkg} installed")
                installed_any = True
            except subprocess.CalledProcessError:
                err(f"Failed to install {pkg} via scoop")
    elif has_choco:
        for pkg in cli_pkgs:
            msg(f"Installing {pkg} via choco...")
            try:
                subprocess.run(["choco", "install", pkg, "-y"], check=True)
                success(f"{pkg} installed")
                installed_any = True
            except subprocess.CalledProcessError:
                err(f"Failed to install {pkg} via choco")
    elif has_winget:
        winget_ids = {"mpv": "mpv-player.mpv", "fzf": "junegunn.fzf"}
        for pkg in cli_pkgs:
            pkg_id = winget_ids.get(pkg, pkg)
            msg(f"Installing {pkg} via winget...")
            try:
                subprocess.run(["winget", "install", "--id", pkg_id, "-e"], check=True)
                success(f"{pkg} installed")
                installed_any = True
            except subprocess.CalledProcessError:
                err(f"Failed to install {pkg} via winget")
    elif has_brew:
        for pkg in cli_pkgs:
            msg(f"Installing {pkg} via brew...")
            try:
                subprocess.run(["brew", "install", pkg], check=True)
                success(f"{pkg} installed")
                installed_any = True
            except subprocess.CalledProcessError:
                err(f"Failed to install {pkg} via brew")
    elif has_apt:
        for pkg in cli_pkgs:
            msg(f"Installing {pkg} via apt...")
            try:
                subprocess.run(["sudo", "apt", "install", "-y", pkg], check=True)
                success(f"{pkg} installed")
                installed_any = True
            except subprocess.CalledProcessError:
                err(f"Failed to install {pkg} via apt")
    elif has_pacman:
        for pkg in cli_pkgs:
            msg(f"Installing {pkg} via pacman...")
            try:
                subprocess.run(["sudo", "pacman", "-S", "--noconfirm", pkg], check=True)
                success(f"{pkg} installed")
                installed_any = True
            except subprocess.CalledProcessError:
                err(f"Failed to install {pkg} via pacman")
    else:
        err("No package manager found (scoop/choco/winget/brew/apt/pacman)")
        warn("Install manually:")
        for pkg in cli_pkgs:
            print(f"    {pkg}: https://{pkg}.io" if pkg == "fzf" else f"    {pkg}: https://mpv.io")

    if installed_any:
        print(f"\n{C.GREEN}Done! You may need to restart your terminal.{C.RESET}\n")
    else:
        print()

def create_alias(alias_name):
    """Create a shell alias/script for ongi-cli"""
    import shutil
    # Find where ongi-cli is installed
    script_path = shutil.which("ongi-cli") or shutil.which("ongi-cli.py")
    if not script_path:
        script_path = os.path.abspath(sys.argv[0])

    created = False

    if sys.platform == "win32":
        # Try scoop shims first
        scoop_shims = Path.home() / "scoop" / "shims"
        if scoop_shims.exists():
            # Create bash launcher
            bash_path = scoop_shims / alias_name
            bash_path.write_text(
                f'#!/usr/bin/env bash\n'
                f'exec ongi-cli "$@"\n',
                encoding='utf-8'
            )
            # Create .cmd for PowerShell/CMD
            cmd_path = scoop_shims / f"{alias_name}.cmd"
            cmd_path.write_text(
                f'@echo off\n'
                f'ongi-cli %*\n',
                encoding='utf-8'
            )
            success(f"Created alias '{alias_name}' in {scoop_shims}")
            msg(f"  Bash:       {bash_path}")
            msg(f"  CMD/PS:     {cmd_path}")
            created = True
        else:
            # Fallback: suggest manual alias
            warn("Scoop shims directory not found.")

        if not created:
            print(f"\n{C.YELLOW}Add manually:{C.RESET}")
            print(f"  Bash:       alias {alias_name}='ongi-cli'")
            print(f"  PowerShell: Set-Alias {alias_name} ongi-cli")
            print(f"  CMD:        doskey {alias_name}=ongi-cli $*")
    else:
        # Unix: add to shell rc
        shell = os.environ.get("SHELL", "/bin/bash")
        if "zsh" in shell:
            rc = Path.home() / ".zshrc"
        elif "fish" in shell:
            rc = Path.home() / ".config" / "fish" / "config.fish"
        else:
            rc = Path.home() / ".bashrc"

        if "fish" in shell:
            alias_line = f"alias {alias_name} 'ongi-cli'"
        else:
            alias_line = f"alias {alias_name}='ongi-cli'"

        # Check if already exists
        if rc.exists() and alias_line in rc.read_text():
            warn(f"Alias '{alias_name}' already exists in {rc}")
            return

        with open(rc, "a") as f:
            f.write(f"\n# ongi-cli alias\n{alias_line}\n")
        success(f"Added alias '{alias_name}' to {rc}")
        msg(f"Run: source {rc}")
        created = True

    if created:
        print(f"\n{C.GREEN}You can now use '{alias_name}' instead of 'ongi-cli'{C.RESET}")

def usage():
    print(f"""
{C.CYAN}ongi-cli{C.RESET} v{VERSION} - Private Anime Streaming CLI

{C.YELLOW}Usage:{C.RESET}
  ongi-cli [options] [search query]

{C.YELLOW}Options:{C.RESET}
  -d, --dub           Stream dubbed version (English)
  -s, --sub           Stream subbed version (default)
  -t, --test          Test all API endpoints
  -H, --history       Show watch history
  --instmissingdep    Install missing dependencies
  --alias <name>      Create a shell alias for ongi-cli
  -h, --help          Show this help message

{C.YELLOW}Controls (after playback):{C.RESET}
  n    Next episode       p    Previous episode
  r    Replay             s    Select episode
  q    Quit

{C.YELLOW}Examples:{C.RESET}
  ongi-cli "one piece"           # Search sub
  ongi-cli -d "naruto"           # Search dub
  ongi-cli --test                # Test APIs
  ongi-cli --alias ani           # Create 'ani' alias
""")

def main():
    mode = "sub"
    query = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-d", "--dub"): mode = "dub"
        elif a in ("-s", "--sub"): mode = "sub"
        elif a in ("-t", "--test"): test_apis(); return
        elif a in ("-H", "--history"): show_history(); return
        elif a == "--instmissingdep": install_missing(); return
        elif a == "--alias":
            i += 1
            if i >= len(args): die("--alias requires a name (e.g. --alias ani)")
            create_alias(args[i]); return
        elif a in ("-h", "--help"): usage(); return
        elif a.startswith("-"): die(f"Unknown option: {a}")
        else: query = a
        i += 1

    # Header
    mode_disp = f"{C.GREEN}DUB{C.RESET} (English)" if mode == "dub" else f"{C.BLUE}SUB{C.RESET} (Japanese)"
    print(f"\n{C.CYAN}+----------------------------------+{C.RESET}")
    print(f"{C.CYAN}|{C.RESET}  ongi-cli v{VERSION}              {C.CYAN}|{C.RESET}")
    print(f"{C.CYAN}|{C.RESET}  Mode: {mode_disp}           {C.CYAN}|{C.RESET}")
    print(f"{C.CYAN}+----------------------------------+{C.RESET}\n")

    if not query:
        try: query = input(f"{C.YELLOW}Search anime: {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt): print(); return
        if not query: die("No search query provided")

    # Search
    msg(f"Searching for: {query} [{mode.upper()}]...")
    try: results = search_anime(query, mode)
    except socket.timeout: die("Search timed out. Check your connection.")
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout): die("Search timed out. Check your connection.")
        die(f"Search failed: {e}")
    except Exception as e: die(f"Search failed: {e}")
    if not results: die("No results found.")
    success(f"Found {len(results)} results")

    # Build display
    display_items = []
    for r in results:
        ep_ct = r.get("availableEpisodes", {}).get(mode, 0)
        if ep_ct > 0:
            display_items.append(f"{r['name']}  ({ep_ct} eps)")
    if not display_items: die(f"No {mode} results for '{query}'")

    # Select anime
    selected = select_item(display_items, "Select anime > ", f"[{mode.upper()}] {len(display_items)} results")
    if not selected:
        warn("No selection made.")
        return
    selected_name = selected.rsplit("  (", 1)[0]
    target = next((r for r in results if r["name"] == selected_name), None)
    if not target: die("Selection error")
    show_id, title = target["_id"], target["name"]
    success(f"Selected: {title}")

    # Get episodes
    msg("Fetching episodes...")
    try: ep_detail = get_episode_list(show_id)
    except Exception as e: die(f"Failed to get episodes: {e}")
    episodes = ep_detail.get(mode, [])
    if not episodes: die(f"No {mode} episodes found")

    def sort_key(ep):
        try: return float(ep)
        except ValueError: return float('inf')
    episodes.sort(key=sort_key)
    success(f"Found {len(episodes)} {mode} episodes")

    # Playback loop
    current_idx = None
    while True:
        if current_idx is None:
            ep_items = [f"Episode {ep}" for ep in episodes]
            sel = select_item(ep_items, "Select episode > ", f"{title} ({len(episodes)} {mode} eps)")
            if not sel: break
            ep_num = sel.replace("Episode ", "")
            current_idx = episodes.index(ep_num) if ep_num in episodes else 0

        ep_no = episodes[current_idx]
        msg(f"Getting sources for episode {ep_no}...")

        try:
            episode_data = get_episode_sources(show_id, mode, ep_no)
        except Exception as e:
            err(f"Failed: {e}"); current_idx = None; continue

        sources = episode_data.get("sourceUrls", [])
        if not sources:
            err(f"No sources for episode {ep_no}"); current_idx = None; continue

        stream_url, provider = get_best_stream(sources)
        if not stream_url:
            err("All sources failed!")
            for s in sources:
                warn(f"  {s.get('sourceName','?')}: {s.get('sourceUrl','?')[:60]}")
            current_idx = None; continue

        save_history(show_id, title, ep_no, mode)
        play_video(stream_url, title, ep_no, provider)

        # Post-playback
        print()
        print(f"{C.CYAN}=== {title} - Episode {ep_no} ==={C.RESET}")
        pos = f"{current_idx + 1}/{len(episodes)}"
        print(f"{C.YELLOW}[n]ext [p]rev [r]eplay [s]elect [q]uit ({pos}):{C.RESET} ", end="")

        try: action = input().strip().lower()
        except (EOFError, KeyboardInterrupt): action = "q"

        if action == "n":
            if current_idx + 1 < len(episodes): current_idx += 1
            else: warn("No next episode"); current_idx = None
        elif action == "p":
            if current_idx > 0: current_idx -= 1
            else: warn("No previous episode"); current_idx = None
        elif action == "r": pass
        elif action == "s": current_idx = None
        elif action in ("q", ""): success("Thanks for watching!"); break
        else: current_idx = None

if __name__ == "__main__":
    main()

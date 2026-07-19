#!/usr/bin/env bash
# Run derpigame locally from a single origin: build the frontend, then serve it
# and the websocket from one process. One command, no per-URL config — each
# client's socket targets whatever origin served the page.
#
#   ./run-local.sh              # http://localhost:8000  (+ your LAN IP)
#   ./run-local.sh --dev        # hot-reload dev: Vite :5173 + backend :8000
#   ./run-local.sh --offline    # dev, but the token-less offline backend
#   ./run-local.sh --share      # also open a public cloudflared tunnel
#   ./run-local.sh --no-build   # skip the rebuild for a faster restart
#   PORT=9000 ./run-local.sh    # backend / serve port (default 8000)
#
# Ctrl+C stops everything it started (dev processes, server, tunnel).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"
share=0 build=1 dev=0 offline=0
for arg in "$@"; do
  case "$arg" in
    --dev) dev=1 ;;
    --offline) dev=1; offline=1 ;;   # offline implies dev; there's no offline serve
    --share) share=1 ;;
    --no-build) build=0 ;;
    -h | --help) sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

[ -x "$ROOT/backend/.venv/bin/uvicorn" ] || { echo "backend venv missing — see README 'Backend > Setup'" >&2; exit 1; }
[ -x "$ROOT/frontend/node_modules/.bin/vite" ] || { echo "frontend deps missing — run 'npm install' in frontend/" >&2; exit 1; }

# Dev mode: run both live processes with hot reload instead of building. Vite
# serves the app on :5173 and talks to the backend via VITE_BACKEND_URL
# (frontend/.env); the backend reloads on code changes. No build, no tunnel.
if [ "$dev" -eq 1 ]; then
  [ "$share" -eq 1 ] && { echo "--dev can't be combined with --share (two origins, no single tunnel)" >&2; exit 2; }

  # Real backend by default; --offline swaps in dev_server (fixed image, no token).
  if [ "$offline" -eq 1 ]; then app="dev_server:app"; app_note="offline, fixed image"
  else app="app.main:app"; app_note="Derpibooru"; fi

  echo
  echo "  derpigame (dev) is starting:"
  echo "    open this  : http://localhost:5173   (Vite, hot reload)"
  echo "    backend    : http://localhost:$PORT   (FastAPI + Socket.IO, --reload, $app_note)"
  echo
  echo "  the frontend reaches the backend via VITE_BACKEND_URL in frontend/.env."
  echo "  Ctrl+C stops both."
  echo

  pids=()
  cleanup() { trap - INT TERM EXIT; kill "${pids[@]}" 2>/dev/null || true; wait 2>/dev/null || true; }
  trap cleanup INT TERM EXIT

  (cd "$ROOT/backend" && exec .venv/bin/uvicorn "$app" --reload --port "$PORT") &
  pids+=($!)
  (cd "$ROOT/frontend" && exec node_modules/.bin/vite) &
  pids+=($!)

  wait -n   # if either process exits, fall through to cleanup and stop the other
  exit
fi

# 1. Build the frontend with an empty backend URL, into a throwaway dir (skips
#    the typecheck in `npm run build` — this just needs to run, not lint).
if [ "$build" -eq 1 ]; then
  echo "==> building frontend -> frontend/dist-local"
  (cd "$ROOT/frontend" && VITE_BACKEND_URL= node_modules/.bin/vite build --base=/ --outDir dist-local)
fi

# 2. Optional public tunnel, started before the server so its URL prints up front.
tunnel_pid=""
if [ "$share" -eq 1 ]; then
  command -v cloudflared >/dev/null || { echo "cloudflared not on PATH — install it or drop --share" >&2; exit 1; }
  log="$(mktemp)"
  cloudflared tunnel --url "http://localhost:$PORT" >"$log" 2>&1 &
  tunnel_pid=$!
  trap '[ -n "$tunnel_pid" ] && kill "$tunnel_pid" 2>/dev/null; rm -f "$log"' EXIT
  echo "==> starting cloudflared tunnel..."
  tunnel_url=""
  for _ in $(seq 1 30); do
    tunnel_url="$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$log" | head -1 || true)"
    [ -n "$tunnel_url" ] && break
    sleep 1
  done
fi

# 3. Show where the game is reachable.
lan_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "  derpigame is starting on port $PORT:"
echo "    this machine : http://localhost:$PORT"
[ -n "$lan_ip" ] && echo "    same network : http://$lan_ip:$PORT   (may need: sudo ufw allow $PORT/tcp)"
if [ "$share" -eq 1 ]; then
  if [ -n "${tunnel_url:-}" ]; then echo "    internet     : $tunnel_url"
  else echo "    internet     : tunnel did not report a URL yet — check its output"; fi
fi
echo

# 4. Serve in the foreground. With a tunnel we must stay the parent so the EXIT
#    trap can stop it on Ctrl+C; otherwise exec and let uvicorn take over.
cd "$ROOT/backend"
if [ "$share" -eq 1 ]; then
  .venv/bin/uvicorn serve:app --host 0.0.0.0 --port "$PORT"
else
  exec .venv/bin/uvicorn serve:app --host 0.0.0.0 --port "$PORT"
fi

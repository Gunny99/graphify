```bash
PROJECT_ROOT=$(pwd -P) || exit 1
if [ -L graphify-out ]; then
    printf '%s\n' 'Refusing to use symlinked graphify-out' >&2
    exit 1
fi
if [ -e graphify-out ] && [ ! -d graphify-out ]; then
    printf '%s\n' 'graphify-out exists but is not a directory' >&2
    exit 1
fi
mkdir -p graphify-out
GRAPHIFY_OUT=$(cd graphify-out && pwd -P) || exit 1
if [ "$GRAPHIFY_OUT" != "$PROJECT_ROOT/graphify-out" ]; then
    printf '%s\n' 'graphify-out resolves outside the project root' >&2
    exit 1
fi
if [ -L graphify-out/.graphify_python ]; then
    printf '%s\n' 'Refusing to read a symlinked Python interpreter marker' >&2
    exit 1
fi
if [ ! -f graphify-out/.graphify_python ]; then
    GRAPHIFY_BIN=$(which graphify 2>/dev/null)
    if [ -n "$GRAPHIFY_BIN" ]; then
        PYTHON=$(head -1 "$GRAPHIFY_BIN" | tr -d '#!')
        case "$PYTHON" in *[!a-zA-Z0-9/_.@-]*) PYTHON="python3" ;; esac
    else
        PYTHON="python3"
    fi
    mkdir -p graphify-out
    "$PYTHON" -c "import sys; open('graphify-out/.graphify_python', 'w', encoding='utf-8').write(sys.executable)"
fi
```

#!/usr/bin/env bash
# Instala OpenJarvis con sus extensiones integradas (OpenClacky + globo 3D)
# en Linux (Ubuntu/Debian) o dentro de WSL2 en Windows 11.
#
#   ./scripts/install-todo-en-uno.sh               # todo
#   ./scripts/install-todo-en-uno.sh --sin-globo   # sin el globo 3D
#   ./scripts/install-todo-en-uno.sh --modelo qwen3:4b
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WITH_GLOBE=true
MODEL="qwen3:8b"
while [[ $# -gt 0 ]]; do
  case $1 in
    --sin-globo) WITH_GLOBE=false ;;
    --modelo) MODEL=$2; shift ;;
    *) echo "Opción desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done
say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

say "1/6 Paquetes del sistema"
if command -v apt-get >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y git curl build-essential libssl-dev libyaml-dev \
    zlib1g-dev libffi-dev pkg-config unzip ca-certificates
else
  echo "Distribución no Debian: instala git, curl y herramientas de compilación a mano."
fi

say "2/6 Ruby 3.3 y Node 24 (con mise)"
if ! command -v mise >/dev/null; then
  curl -fsSL https://mise.run | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
grep -q 'mise activate' ~/.bashrc 2>/dev/null \
  || echo 'eval "$(~/.local/bin/mise activate bash)"' >> ~/.bashrc
eval "$(mise activate bash)"
mise use -g ruby@3.3 node@24
eval "$(mise activate bash)"

say "3/6 uv y Ollama"
command -v uv >/dev/null || { curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }
if grep -qi microsoft /proc/version 2>/dev/null \
   && curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama de Windows detectado desde WSL (usa tu GPU)."
elif ! command -v ollama >/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

say "4/6 OpenJarvis"
cd "$ROOT"
uv sync --extra server --extra desktop --extra tools-search --extra inference-cloud

say "5/6 Extensiones"
( cd extensions/clacky && bundle install )
if $WITH_GLOBE; then
  ( cd extensions/globe && npm ci )
fi
( cd frontend && npx -y npm@11 ci )

say "6/6 Configuración y modelo"
CONFIG_DIR="${OPENJARVIS_HOME:-$HOME/.openjarvis}"
mkdir -p "$CONFIG_DIR"
CONFIG="$CONFIG_DIR/config.toml"
touch "$CONFIG"
add_section() { grep -q "^\[$1\]" "$CONFIG" || printf '\n[%s]\n%s\n' "$1" "$2" >> "$CONFIG"; }
add_section analytics "enabled = false"
add_section intelligence "default_model = \"$MODEL\""
if ! $WITH_GLOBE; then add_section extensions.globe "enabled = false"; fi
if command -v ollama >/dev/null; then
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || (ollama serve >/dev/null 2>&1 &)
  sleep 2
  ollama pull "$MODEL"
fi

cat <<EOF

✅ Listo. Abre una terminal nueva y ejecuta:

   cd $ROOT && uv run jarvis gui

Se abre una sola app con Chat, Globe y Clacky en la barra lateral.
Configuración: $CONFIG
EOF

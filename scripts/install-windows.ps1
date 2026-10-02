# Instalador para Windows 11 (PowerShell como administrador):
#   Set-ExecutionPolicy -Scope Process Bypass; .\scripts\install-windows.ps1
#
# Todo corre dentro de WSL2 (Ubuntu): el mismo código que en Linux, así que si
# cambias la laptop a Linux no cambia nada. Ollama se instala en Windows para
# usar tu GPU y la red "mirrored" deja que Windows y Ubuntu compartan localhost.
$ErrorActionPreference = "Stop"
function Say($m) { Write-Host "`n== $m" -ForegroundColor Cyan }

Say "1/4 WSL2 + Ubuntu"
$distros = (wsl.exe -l -q 2>$null) -replace "`0", ""
if (-not ($distros -match "Ubuntu")) {
    wsl.exe --install -d Ubuntu
    Write-Host "Reinicia Windows, abre 'Ubuntu' una vez para crear tu usuario y vuelve a ejecutar este script." -ForegroundColor Yellow
    exit 0
}
$wslcfg = Join-Path $env:USERPROFILE ".wslconfig"
if (-not (Test-Path $wslcfg) -or -not (Select-String -Path $wslcfg -Pattern "networkingMode" -Quiet)) {
    Add-Content $wslcfg "`n[wsl2]`nnetworkingMode=mirrored"
    wsl.exe --shutdown
}

Say "2/4 Ollama para Windows (GPU)"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
}

Say "3/4 Chrome (para que el agente pueda usar tu navegador)"
winget install -e --id Google.Chrome --accept-source-agreements --accept-package-agreements 2>$null

Say "4/4 Clonar e instalar dentro de Ubuntu"
$repo = Read-Host "URL de tu repo (ej. https://github.com/TU_USUARIO/jarvis.git)"
$branch = Read-Host "Rama (Enter para la rama por defecto)"
$clone = if ($branch) { "git clone -b '$branch' '$repo' ~/jarvis" } else { "git clone '$repo' ~/jarvis" }
wsl.exe -d Ubuntu -- bash -lc "test -d ~/jarvis || $clone; cd ~/jarvis && ./scripts/install-todo-en-uno.sh"

Write-Host "`nListo. Abre 'Ubuntu' y escribe:  cd ~/jarvis && uv run jarvis gui" -ForegroundColor Green

# run_demo.ps1 — запуск демо Onvy с доступом СО ВСЕХ УСТРОЙСТВ (телефоны тоже).
# Поднимает сервер + HTTPS-туннель cloudflared и печатает публичную ссылку.
# Логин (ключ доступа) на демо: 12345

$ErrorActionPreference = "SilentlyContinue"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proj

$port = 8080
$cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

if (-not (Test-Path $cf)) {
    Write-Host "cloudflared не найден. Установи: winget install --id Cloudflare.cloudflared" -ForegroundColor Red
    Read-Host "Enter для выхода"; exit 1
}

Write-Host "Останавливаю прошлые запуски..." -ForegroundColor DarkGray
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn app.main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Get-Process cloudflared -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 2

Write-Host "Запускаю сервер Onvy на порту $port..." -ForegroundColor Cyan
Start-Process -WindowStyle Minimized -FilePath "uv" -ArgumentList "run","uvicorn","app.main:app","--host","0.0.0.0","--port","$port" -WorkingDirectory $proj
Start-Sleep 6

$log = Join-Path $env:TEMP "onvy_cf.log"
$errlog = Join-Path $env:TEMP "onvy_cf.err.log"
Remove-Item $log,$errlog -EA SilentlyContinue

Write-Host "Открываю HTTPS-туннель..." -ForegroundColor Cyan
Start-Process -WindowStyle Minimized -FilePath $cf -ArgumentList "tunnel","--url","http://localhost:$port","--no-autoupdate" -RedirectStandardOutput $log -RedirectStandardError $errlog

$url = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep 1
    $m = Select-String -Path $log,$errlog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -EA SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value; break }
}

Write-Host ""
if ($url) {
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host "  ССЫЛКА (открой на ноутбуке и раздай телефонам):" -ForegroundColor Green
    Write-Host "  $url" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  ЛОГИН (ключ доступа): 12345" -ForegroundColor Yellow
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Менеджер: открой ссылку -> роль 'Менеджер' -> покажи QR."
    Write-Host "Жюри: сканируют QR телефоном -> вводят имя и язык."
} else {
    Write-Host "Не удалось получить публичную ссылку. Смотри лог: $log" -ForegroundColor Red
}

Write-Host ""
Write-Host "НЕ ЗАКРЫВАЙ это окно во время демо." -ForegroundColor DarkYellow
Read-Host "Нажми Enter, чтобы остановить демо"

Get-Process cloudflared -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn app.main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Write-Host "Демо остановлено."

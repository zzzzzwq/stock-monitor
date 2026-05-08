# 盯盘助手 — Windows 本地启动脚本
# 用法: 在 PowerShell 中运行 .\start.ps1

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv" "Scripts" "python.exe"

# 检查虚拟环境
if (-not (Test-Path $VenvPython)) {
    Write-Host "创建虚拟环境..." -ForegroundColor Yellow
    python -m venv "$ProjectRoot\.venv"
    & "$VenvPython" -m pip install -r "$ProjectRoot\requirements.txt"
}

Write-Host "=== 盯盘助手 — 本地启动 ===" -ForegroundColor Green
Write-Host ""

# 迁移旧配置到数据库
& $VenvPython "$ProjectRoot\main.py" --migrate-config

# 启动服务（开发模式，非交易日也能看到数据）
Write-Host "启动 Flask 服务: http://localhost:8080" -ForegroundColor Green
Write-Host "健康检查: http://localhost:8080/health" -ForegroundColor Green
Write-Host "按 Ctrl+C 停止" -ForegroundColor Yellow
Write-Host ""

& $VenvPython "$ProjectRoot\main.py"

# 盯盘助手 — 自动同步到 GitHub
# 用法:
#   手动同步:  .\sync.ps1
#   设为定时任务: 把下面这行加到 Windows 任务计划程序
#   powershell.exe -File "C:\Users\76719\stock-monitor\sync.ps1"

$ProjectRoot = "C:\Users\76719\stock-monitor"
$LogFile = Join-Path $ProjectRoot "logs\sync.log"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts $msg" | Out-File -FilePath $LogFile -Encoding utf8 -Append
    Write-Host $msg
}

Set-Location $ProjectRoot

$status = git status --porcelain
if (-not $status) {
    Log "[sync] 无变更，跳过"
    exit 0
}

Log "[sync] 检测到变更，开始同步..."
Log $status

git add -A 2>&1 | Out-Null

$msg = "auto sync $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git commit -m $msg 2>&1 | ForEach-Object { Log $_ }
git push origin master 2>&1 | ForEach-Object { Log $_ }

Log "[sync] 同步完成"

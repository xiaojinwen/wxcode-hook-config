param(
    [string]$Branch = "master",
    [switch]$NoFetch
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  正在同步到 Gitee 和 GitHub ..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否有未提交的变更
$status = git status --short
if ($status) {
    Write-Host "未提交的变更:" -ForegroundColor Yellow
    git status --short
    Write-Host ""
    $choice = Read-Host "有未提交的变更，是否继续推送? (y/N)"
    if ($choice -ne "y" -and $choice -ne "Y") {
        Write-Host "已取消推送。" -ForegroundColor Red
        exit 1
    }
}

# 推送到 GitHub (origin)
Write-Host "[1/2] 推送到 GitHub (origin) ..." -ForegroundColor Green
git push origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] GitHub 推送失败，继续尝试 Gitee ..." -ForegroundColor Yellow
} else {
    Write-Host "[OK] GitHub 推送成功" -ForegroundColor Green
}
Write-Host ""

# 推送到 Gitee
Write-Host "[2/2] 推送到 Gitee ..." -ForegroundColor Green
git push gitee $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Gitee 推送失败" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Gitee 推送成功" -ForegroundColor Green
}
Write-Host ""

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  同步完成！" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

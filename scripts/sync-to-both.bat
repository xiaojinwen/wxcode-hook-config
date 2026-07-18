@echo off
chcp 65001 >nul
title 同步到 Gitee + GitHub

echo ============================================
echo  正在同步到 Gitee 和 GitHub ...
echo ============================================
echo.

:: 先提交本地变更（如果有未提交的）
git status --short
echo.
echo 如果上面有未提交的变更，请先提交: git add . ^&^& git commit -m "your message"
echo.

:: 推送到 GitHub (origin)
echo [1/2] 推送到 GitHub (origin) ...
git push origin master
if %ERRORLEVEL% NEQ 0 (
    echo [!] GitHub 推送失败，继续尝试 Gitee ...
) else (
    echo [OK] GitHub 推送成功
)
echo.

:: 推送到 Gitee
echo [2/2] 推送到 Gitee ...
git push gitee master
if %ERRORLEVEL% NEQ 0 (
    echo [!] Gitee 推送失败
) else (
    echo [OK] Gitee 推送成功
)
echo.

echo ============================================
echo  同步完成！
echo ============================================
pause

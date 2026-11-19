@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   打包 网页转文件-剪藏助手 V1.1.0 预览版 (GUI)
echo ============================================
echo.

REM 自动探测带 tkinter 的 Python（GUI 需要 tkinter，部分精简版 Python 不含）
set "PY="
for %%C in (python python3 py) do (
  if not defined PY (
    %%C -c "import tkinter" >nul 2>nul && set "PY=%%C"
  )
)
if not defined PY (
  echo [错误] 未找到带 tkinter 的 Python。请安装官方 CPython 3.10+ 后重试。
  echo.
  pause
  exit /b 1
)
echo 使用解释器: %PY%

echo 检查打包依赖...
%PY% -c "import PyInstaller" >nul 2>nul || %PY% -m pip install pyinstaller
%PY% -c "import docx" >nul 2>nul || %PY% -m pip install -r requirements.txt
echo.

%PY% -m PyInstaller build.spec --noconfirm

echo.
if exist "dist\网页转文件-剪藏助手-V1.1.0预览版.exe" (
  echo [成功] 已生成：dist\网页转文件-剪藏助手-V1.1.0预览版.exe
  for %%F in ("dist\网页转文件-剪藏助手-V1.1.0预览版.exe") do echo [体积] %%~zF 字节
) else (
  echo [失败] 未找到 exe，请查看上方错误信息。
)
echo.
pause

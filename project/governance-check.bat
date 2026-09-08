@echo off
setlocal
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
where python >nul 2>&1
if errorlevel 1 (
  echo GOV-BOOT-001: python is unavailable on PATH. 1>&2
  exit /b 1
)
if exist "%REPO_ROOT%\.governance\governance_check.py" (
  python -B "%REPO_ROOT%\.governance\governance_check.py" --root "%REPO_ROOT%" --manifest .governance/manifest.json --lock .governance/manifest.lock.json --stack-profiles .governance/stack-profiles.json %*
) else (
  python -B "%REPO_ROOT%\scripts\governance_check.py" --root "%REPO_ROOT%" --manifest governance\manifest.hub.json --stack-profiles governance\stack-profiles.json --work-classification governance\work-classification.dsl.json %*
)
set "GOVERNANCE_EXIT=%ERRORLEVEL%"
exit /b %GOVERNANCE_EXIT%

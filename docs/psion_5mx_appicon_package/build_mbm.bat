@echo off
where bmconv >nul 2>nul || (echo ERROR: BMCONV.EXE not found in PATH.& exit /b 1)
bmconv bmconv.cmd
if errorlevel 1 exit /b %errorlevel%
bmconv /v appicon.mbm

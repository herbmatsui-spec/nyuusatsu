@echo off
cd /d %~dp0
echo Starting RQ Worker...
py -3 scripts/run_rq_worker.py
pause

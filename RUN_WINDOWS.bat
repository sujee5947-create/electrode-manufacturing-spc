@echo off
chcp 65001 > nul
cd /d "%~dp0"
python main.py --raw "raw data/Electrode_Quality_Raw_Data.csv" --spec "raw data/Electrode_Quality_SPEC.xlsx" --output result
if errorlevel 1 (
  echo [ERROR] Analysis stopped. Check input and Python packages.
) else (
  echo [OK] Reports created in result folder.
)
pause

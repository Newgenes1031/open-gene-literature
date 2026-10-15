@echo off
cd /d "%~dp0"
py -3 gene_literature_gui.py
if errorlevel 1 (
  echo GUI could not start. Install Python and run: py -3 -m pip install .
  pause
)

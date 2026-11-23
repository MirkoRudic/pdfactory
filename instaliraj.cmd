@echo off
rem PDFabrika - instalacija. Pokreće je Instaliraj.vbs (prozor umanjen, izlaz u data\logs\instalacija.log).
cd /d "%~dp0"
if not exist data\logs mkdir data\logs
set LOG=data\logs\instalacija.log
echo %date% %time% instalacija > %LOG%
if not exist .venv (
  where py >nul 2>nul && (py -3 -m venv .venv >> %LOG% 2>&1) || (python -m venv .venv >> %LOG% 2>&1)
)
".venv\Scripts\python.exe" -m pip install --upgrade pip >> %LOG% 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt >> %LOG% 2>&1 || goto :err
if exist "D:\VAJB\kontrolaizbora\podaci\ocr\tessdata\srp.traineddata" (
  copy /y "D:\VAJB\kontrolaizbora\podaci\ocr\tessdata\srp*.traineddata" tessdata\ >> %LOG% 2>&1
)
start "" ".venv\Scripts\pythonw.exe" PDFabrika.pyw --instaliraj
exit /b 0
:err
echo GRESKA >> %LOG%
start "" notepad %LOG%
exit /b 1

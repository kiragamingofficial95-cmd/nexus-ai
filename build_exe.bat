@echo off
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name NexusAI --collect-all customtkinter app.py
echo.
echo Built: dist\NexusAI.exe
pause

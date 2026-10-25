Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\EmilioR\.gemini\antigravity\scratch\dynamic-island"
WshShell.Run """C:\Users\EmilioR\AppData\Local\Microsoft\WindowsApps\pythonw.exe"" main.py", 0, False

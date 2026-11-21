Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "G:\VDGP"
sh.Run """G:\VDGP\.venv\Scripts\pythonw.exe"" -m gcf gui", 1, False

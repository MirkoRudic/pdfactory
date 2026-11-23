' PDFabrika - instalacija jednim dvoklikom: paketi, prečica na desktopu, start sa Windows-om, PDF program.
Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
sh.Run "cmd /c """ & dir & "\instaliraj.cmd""", 7, False

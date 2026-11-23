' PDFabrika - instalacija jednim dvoklikom (prozor sa napretkom: instaliraj.pyw).
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
dir = fs.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
On Error Resume Next
sh.Run "pyw.exe -3 """ & dir & "\instaliraj.pyw""", 1, False
If Err.Number <> 0 Then
  Err.Clear
  sh.Run "pythonw.exe """ & dir & "\instaliraj.pyw""", 1, False
  If Err.Number <> 0 Then MsgBox "Python nije pronađen na ovom računaru.", 16, "PDFabrika"
End If

' PDFactory - setup with one double click (progress window: instaliraj.pyw).
' Without Python on the computer it first installs Python with winget (comes with Windows 10/11).
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
dir = fs.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir

Function Has(cmd)
  Has = (sh.Run("cmd /c where " & cmd & " >nul 2>nul", 0, True) = 0)
End Function

If Not (Has("pyw.exe") Or Has("pythonw.exe")) Then
  If MsgBox("PDFactory needs Python. Install it now (about 1 minute)?", 36, "PDFactory") <> 6 Then WScript.Quit
  rc = sh.Run("winget install -e --id Python.Python.3.13 --scope user --silent --accept-package-agreements --accept-source-agreements", 7, True)
  ' winget puts Python on PATH only for new processes: use the py launcher from its known place
  py = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe")
  If Not fs.FileExists(py) Then py = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe")
  If Not fs.FileExists(py) Then
    MsgBox "Python could not be installed. Install it from python.org and run setup again.", 16, "PDFactory"
    WScript.Quit
  End If
  If InStr(LCase(py), "pyw.exe") > 0 Then
    sh.Run """" & py & """ -3 """ & dir & "\instaliraj.pyw""", 1, False
  Else
    sh.Run """" & py & """ """ & dir & "\instaliraj.pyw""", 1, False
  End If
  WScript.Quit
End If

If Has("pyw.exe") Then
  sh.Run "pyw.exe -3 """ & dir & "\instaliraj.pyw""", 1, False
Else
  sh.Run "pythonw.exe """ & dir & "\instaliraj.pyw""", 1, False
End If

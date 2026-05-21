Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(fso.GetParentFolderName(folder))
shell.CurrentDirectory = root
shell.Run "cmd /c ""scripts\windows\run_desktop_mentor.bat""", 0, False

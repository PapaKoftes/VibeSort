' Vibesort launcher — opens the app without a terminal window flash
' Double-click this OR the desktop shortcut to launch.
Option Explicit
Dim WshShell, Here
Set WshShell = CreateObject("WScript.Shell")
Here = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
WshShell.Run "cmd /c """ & Here & "run.bat""", 0, False

If WinExists("YJSNPIbot") Then
WinActivate("YJSNPIbot")
Send("^c")
Sleep(1000)
Send("y")
Sleep(1000)
Send("{Enter}")
Sleep(5000)
ShellExecute(@ScriptDir & "\..\__YJSNPI_bot_start.bat")
EndIf
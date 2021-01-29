If WinExists("Mine-Vanilla") Then
WinActivate("Mine-Vanilla")
Send("stop")
Send("{Enter}")
Sleep(3000)
Send("exit")
Send("{Enter}")
EndIf
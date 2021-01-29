If WinExists("Mine-Knee") Then
WinActivate("Mine-Knee")
Send("stop")
Send("{Enter}")
Sleep(3000)
Send("exit")
Send("{Enter}")
EndIf
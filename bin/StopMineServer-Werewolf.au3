If WinExists("Mine-Werewolf") Then
WinActivate("Mine-Werewolf")
Send("stop")
Send("{Enter}")
Sleep(3000)
Send("exit")
Send("{Enter}")
EndIf
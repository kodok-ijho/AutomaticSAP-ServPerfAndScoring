On Error Resume Next
Set sap = CreateObject("Sapgui.ScriptingCtrl.1")
If Err.Number = 0 Then
    WScript.Echo "ScriptingCtrl OK"
Else
    WScript.Echo "ScriptingCtrl Error: " & Err.Description
End If

Set sap2 = GetObject("SAPGUI")
If Err.Number = 0 Then
    WScript.Echo "GetObject SAPGUI OK"
Else
    WScript.Echo "GetObject SAPGUI Error: " & Err.Description
End If

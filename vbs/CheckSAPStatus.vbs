On Error Resume Next
Dim SapGuiAuto, application

Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    Err.Clear
    Set SapGuiAuto = CreateObject("Sapgui.ScriptingCtrl.1")
End If

If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    WScript.Echo "NO_SAPGUI"
    WScript.Quit 1
End If

Set application = SapGuiAuto.GetScriptingEngine
If Err.Number <> 0 Or application Is Nothing Then
    WScript.Echo "NO_ENGINE"
    WScript.Quit 1
End If

If application.Children.Count = 0 Then
    WScript.Echo "NO_CONN"
    WScript.Quit 1
End If

Dim i, connCheck, foundSession
Set foundSession = Nothing
For i = 0 To application.Children.Count - 1
    Set connCheck = application.Children(CInt(i))
    If connCheck.Children.Count > 0 Then
        Set foundSession = connCheck.Children(0)
        Exit For
    End If
Next

If foundSession Is Nothing Then
    WScript.Echo "NO_SESS"
    WScript.Quit 1
End If

Err.Clear
foundSession.findById("wnd[0]/usr/txtRSYST-BNAME")
If Err.Number = 0 Then
    WScript.Echo "LOGIN_SCREEN"
    WScript.Quit 1
End If

WScript.Echo "LOGGED_IN"
WScript.Quit 0

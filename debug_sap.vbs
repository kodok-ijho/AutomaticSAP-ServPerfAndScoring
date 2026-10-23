On Error Resume Next
Err.Clear
Set SapGuiAuto = GetObject("SAPGUI")
WScript.Echo "Err.Number: " & Err.Number & " | Err.Desc: " & Err.Description
If SapGuiAuto Is Nothing Then
    WScript.Echo "SapGuiAuto is Nothing"
Else
    WScript.Echo "SapGuiAuto is Object: " & TypeName(SapGuiAuto)
    Set app = SapGuiAuto.GetScriptingEngine
    WScript.Echo "App is Object: " & TypeName(app) & " | Children: " & app.Children.Count
    If app.Children.Count > 0 Then
        Set conn = app.Children(0)
        WScript.Echo "Conn Children: " & conn.Children.Count
        If conn.Children.Count > 0 Then
            Set sess = conn.Children(0)
            WScript.Echo "Session Active Window: " & sess.ActiveWindow.Text
        End If
    End If
End If

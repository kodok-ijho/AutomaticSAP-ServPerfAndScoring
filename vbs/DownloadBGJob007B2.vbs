' --- Kondisi Sebelum Menjalankan ---
On Error Resume Next
Dim bNeedLogin
bNeedLogin = False

Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Then
    bNeedLogin = True
ElseIf SapGuiAuto.GetScriptingEngine.Children.Count = 0 Then
    bNeedLogin = True
Else
    ' Cari apakah ada session aktif
    Dim i, connCheck, foundSessCheck
    Set foundSessCheck = Nothing
    Set appCheck = SapGuiAuto.GetScriptingEngine
    For i = 0 To appCheck.Children.Count - 1
        Set connCheck = appCheck.Children(CInt(i))
        If connCheck.Children.Count > 0 Then
            Set foundSessCheck = connCheck.Children(0)
            Exit For
        End If
    Next
    
    If foundSessCheck Is Nothing Then
        bNeedLogin = True
    Else
        ' Cek apakah foundSessCheck itu berada di layar login
        Err.Clear
        foundSessCheck.findById("wnd[0]/usr/txtRSYST-BNAME")
        If Err.Number = 0 Then
            bNeedLogin = True
        End If
    End If
End If
On Error GoTo 0

If bNeedLogin Then
    Set Shell = CreateObject("WScript.Shell")
    strPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
    Shell.Run "wscript.exe """ & strPath & "LoginSAP.vbs""", 1, True
    Set SapGuiAuto = GetObject("SAPGUI")
End If
' ------------------------------------

If Not IsObject(application) Then
   Set application = SapGuiAuto.GetScriptingEngine
End If

' Cari koneksi dan session yang aktif
Dim activeConn, activeSess
Set activeConn = Nothing
Set activeSess = Nothing
For i = 0 To application.Children.Count - 1
    Set connCheck = application.Children(CInt(i))
    If connCheck.Children.Count > 0 Then
        Set activeConn = connCheck
        Set activeSess = connCheck.Children(0)
        Exit For
    End If
Next

If activeConn Is Nothing Or activeSess Is Nothing Then
    MsgBox "Error: Tidak ada session SAP yang aktif!"
    WScript.Quit
End If

Set connection = activeConn
Set session = activeSess

If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nzsmr007b"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtS_BUDAT-LOW").text = "301225"
session.findById("wnd[0]/usr/ctxtS_BUDAT-HIGH").text = "280126"
session.findById("wnd[0]/usr/ctxtP_VARI").setFocus
session.findById("wnd[0]/usr/ctxtP_VARI").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 4
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/5[0,5]/lbl[1,5]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/5[0,5]/lbl[1,5]").caretPosition = 8
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/usr/btn%_S_EQUNR_%_APP_%-VALU_PUSH").press
session.findById("wnd[1]/tbar[0]/btn[16]").press
session.findById("wnd[1]/tbar[0]/btn[24]").press
session.findById("wnd[1]/tbar[0]/btn[8]").press
session.findById("wnd[0]/mbar/menu[0]/menu[2]").select
session.findById("wnd[1]/tbar[0]/btn[13]").press
session.findById("wnd[1]/usr/btnDATE_PUSH").press
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTDT").text = "280426"
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").text = "180000"
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").setFocus
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").caretPosition = 6
session.findById("wnd[1]").sendVKey 0
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[11]").press
session.findById("wnd[0]").sendVKey 4
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/6[0,6]/lbl[14,6]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/6[0,6]/lbl[14,6]").caretPosition = 10
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[2]").select
session.findById("wnd[1]/tbar[0]/btn[13]").press
session.findById("wnd[1]/usr/btnDATE_PUSH").press
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTDT").text = "280426"
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").text = "180000"
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").setFocus
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").caretPosition = 6
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[11]").press

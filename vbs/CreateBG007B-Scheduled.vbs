' --- Kondisi Sebelum Menjalankan ---
On Error Resume Next
Dim bNeedLogin
bNeedLogin = False

Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    bNeedLogin = True
ElseIf SapGuiAuto.GetScriptingEngine.Children.Count = 0 Then
    bNeedLogin = True
Else
    ' Cek apakah ada di layar login
    Set sessionCheck = SapGuiAuto.GetScriptingEngine.Children(0).Children(0)
    sessionCheck.findById("wnd[0]/usr/txtRSYST-BNAME")
    If Err.Number = 0 Then
        bNeedLogin = True
    End If
End If
On Error GoTo 0

If bNeedLogin Then
    Set Shell = CreateObject("WScript.Shell")
    strPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
    Shell.Run "cscript.exe //Nologo """ & strPath & "LoginSAP.vbs""", 1, True
    Set SapGuiAuto = GetObject("SAPGUI")
End If
' ------------------------------------

If Not IsObject(application) Then
   Set application = SapGuiAuto.GetScriptingEngine
End If

' Cari koneksi dan session yang aktif
Dim activeConn, activeSess, i, connCheck
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
    WScript.Echo "ERROR: Tidak ada session SAP yang aktif!"
    WScript.Quit 1
End If

Set connection = activeConn
Set session    = activeSess

If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If

' Ambil argumen dari Python
Set args = WScript.Arguments
If args.Count < 5 Then
    MsgBox "Error: Butuh 5 argumen (startDate, endDate, schedDate, schedTime1, schedTime2)."
    WScript.Quit
End If

startDate  = args(0)
endDate    = args(1)
schedDate  = args(2)
schedTime1 = args(3)
schedTime2 = args(4)

session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nzsmr007b"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtS_BUDAT-LOW").text = startDate
session.findById("wnd[0]/usr/ctxtS_BUDAT-HIGH").text = endDate
session.findById("wnd[0]/usr/ctxtP_VARI").text = "LAYOUTMINI1"
session.findById("wnd[0]/usr/ctxtP_VARI").setFocus
session.findById("wnd[0]/usr/ctxtP_VARI").caretPosition = 11
session.findById("wnd[0]/usr/btn%_S_EQUNR_%_APP_%-VALU_PUSH").press
session.findById("wnd[1]/tbar[0]/btn[16]").press
session.findById("wnd[1]/tbar[0]/btn[24]").press
session.findById("wnd[1]/tbar[0]/btn[8]").press
session.findById("wnd[0]/mbar/menu[0]/menu[2]").select
session.findById("wnd[1]/tbar[0]/btn[13]").press
session.findById("wnd[1]/usr/btnDATE_PUSH").press
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTDT").text = schedDate
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").text = schedTime1
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").setFocus
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").caretPosition = 6


session.findById("wnd[1]").sendVKey 0
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[11]").press
session.findById("wnd[0]/usr/ctxtP_VARI").text = "LAYOUTMINI2"
session.findById("wnd[0]").sendVKey 9
session.findById("wnd[1]/tbar[0]/btn[13]").press
session.findById("wnd[1]/usr/btnDATE_PUSH").press
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTDT").text = schedDate
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").text = schedTime2
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").setFocus
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").caretPosition = 4
session.findById("wnd[1]").sendVKey 0
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[11]").press
session.findById("wnd[0]").sendVKey 3

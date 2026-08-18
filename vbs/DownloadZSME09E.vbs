' === ASUMSI: SAP SUDAH LOGIN. Tidak ada proses login otomatis di sini. ===
On Error Resume Next
Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Then
    MsgBox "Error: SAP GUI tidak berjalan. Buka SAP dan login terlebih dahulu."
    WScript.Quit
End If
On Error GoTo 0

If SapGuiAuto Is Nothing Then
    MsgBox "Error: SAP GUI tidak tersedia. Buka SAP dan login terlebih dahulu."
    WScript.Quit
End If

Set application = SapGuiAuto.GetScriptingEngine

' Cari koneksi & session yang aktif (diasumsikan sudah login)
Dim i, connCheck, activeConn, activeSess
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
    MsgBox "Error: Tidak ada session SAP yang aktif. Pastikan SAP sudah login."
    WScript.Quit
End If

Set connection = activeConn
Set session = activeSess

If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If

' --- TERIMA PARAMETER DARI PYTHON ---
Set args = WScript.Arguments
If args.Count < 4 Then
    MsgBox "Error: Butuh 4 argumen (fromDate, toDate, savePath, fileName)."
    WScript.Quit
End If

fromDate = args(0)
toDate   = args(1)
savePath = args(2)
fileName = args(3)
' ------------------------------------

session.findById("wnd[0]").maximize

session.findById("wnd[0]/tbar[0]/okcd").text = "/nzsme09e"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtSP$00005-LOW").text = fromDate
session.findById("wnd[0]/usr/ctxtSP$00005-HIGH").text = toDate
session.findById("wnd[0]/usr/txtSP$00012-LOW").text = ""
session.findById("wnd[0]/usr/ctxtSP$00010-LOW").text = ""
session.findById("wnd[0]/usr/ctxtSP$00010-LOW").setFocus
session.findById("wnd[0]/usr/ctxtSP$00010-LOW").caretPosition = 0
session.findById("wnd[0]/tbar[1]/btn[8]").press
session.findById("wnd[0]/mbar/menu[0]/menu[3]/menu[2]").select
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[1]/usr/ctxtDY_PATH").setFocus
session.findById("wnd[1]/usr/ctxtDY_PATH").caretPosition = 0
session.findById("wnd[1]").sendVKey 4
session.findById("wnd[2]/usr/ctxtDY_PATH").setFocus
session.findById("wnd[2]/usr/ctxtDY_PATH").caretPosition = 38
session.findById("wnd[2]").sendVKey 4
session.findById("wnd[3]/usr/ctxtDY_PATH").text = savePath
session.findById("wnd[3]/usr/ctxtDY_FILENAME").text = fileName
session.findById("wnd[3]/usr/ctxtDY_FILENAME").caretPosition = Len(fileName)
session.findById("wnd[3]/tbar[0]/btn[0]").press
session.findById("wnd[2]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press

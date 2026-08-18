' === ZSMR019 SAP GUI Automation Script ===
' Param (opsional dari CLI): fromDate, toDate, savePath, fileName
On Error Resume Next
Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Then
    MsgBox "Error: SAP GUI tidak berjalan. Buka SAP dan login terlebih dahulu."
    WScript.Quit 1
End If
On Error GoTo 0

If SapGuiAuto Is Nothing Then
    MsgBox "Error: SAP GUI tidak tersedia. Buka SAP dan login terlebih dahulu."
    WScript.Quit 1
End If

Set application = SapGuiAuto.GetScriptingEngine

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
    WScript.Quit 1
End If

Set connection = activeConn
Set session = activeSess

If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If

' --- PARAMETER HANDLING ---
Dim fromDate, toDate, savePath, fileName
Dim args
Set args = WScript.Arguments

If args.Count >= 4 Then
    fromDate = args(0)
    toDate   = args(1)
    savePath = args(2)
    fileName = args(3)
Else
    fromDate = "27.06.2026"
    toDate   = "29.07.2026"
    savePath = "D:\Kerja\SS\"
    fileName = "ZSMR019.txt"
End If

session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nzsmr019"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/tbar[1]/btn[17]").press
session.findById("wnd[1]/usr/txtENAME-LOW").text = ""
session.findById("wnd[1]/usr/txtENAME-LOW").setFocus
session.findById("wnd[1]/usr/txtENAME-LOW").caretPosition = 0
session.findById("wnd[1]/tbar[0]/btn[8]").press
session.findById("wnd[1]/usr/cntlALV_CONTAINER_1/shellcont/shell").currentCellRow = 23
session.findById("wnd[1]/usr/cntlALV_CONTAINER_1/shellcont/shell").firstVisibleRow = 9
session.findById("wnd[1]/usr/cntlALV_CONTAINER_1/shellcont/shell").selectedRows = "23"
session.findById("wnd[1]/usr/cntlALV_CONTAINER_1/shellcont/shell").doubleClickCurrentCell
session.findById("wnd[0]/usr/ctxtSP$00011-LOW").text = fromDate
session.findById("wnd[0]/usr/ctxtSP$00011-HIGH").text = toDate
session.findById("wnd[0]/usr/ctxtSP$00011-HIGH").setFocus
session.findById("wnd[0]/usr/ctxtSP$00011-HIGH").caretPosition = 10
session.findById("wnd[0]/tbar[1]/btn[8]").press
session.findById("wnd[0]/mbar/menu[0]/menu[3]/menu[2]").select
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[1]/usr/ctxtDY_PATH").setFocus
session.findById("wnd[1]/usr/ctxtDY_PATH").caretPosition = 0
session.findById("wnd[1]").sendVKey 4
session.findById("wnd[2]").sendVKey 4
session.findById("wnd[3]/usr/ctxtDY_PATH").text = savePath
session.findById("wnd[3]/usr/ctxtDY_FILENAME").text = fileName
session.findById("wnd[3]/usr/ctxtDY_FILENAME").caretPosition = Len(fileName)
session.findById("wnd[3]/tbar[0]/btn[0]").press
session.findById("wnd[2]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[0]").press

' --- POPUP OVERWRITE & NAVIGASI KEMBALI (OPSIONAL) ---
On Error Resume Next
session.findById("wnd[1]/usr/btnSPOP-OPTION1").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[1]/usr/btnSPOP-OPTION1").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
On Error GoTo 0

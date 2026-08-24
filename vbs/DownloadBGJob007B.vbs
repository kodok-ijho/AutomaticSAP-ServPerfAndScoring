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

' Ambil argumen dari Python
Set args = WScript.Arguments
If args.Count < 3 Then
    MsgBox "Error: Butuh 3 argumen (fromDate, toDate, savePath)."
    WScript.Quit
End If
fromDate = args(0)
toDate   = args(1)
savePath = args(2)

session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nsm37"
session.findById("wnd[0]").sendVKey 0

' Filter Status: Hanya cari yang FINISHED
session.findById("wnd[0]/usr/chkBTCH2170-PRELIM").selected = false
session.findById("wnd[0]/usr/chkBTCH2170-SCHED").selected  = false
session.findById("wnd[0]/usr/chkBTCH2170-READY").selected  = false
session.findById("wnd[0]/usr/chkBTCH2170-RUN").selected    = false
session.findById("wnd[0]/usr/chkBTCH2170-FINISH").selected = true
session.findById("wnd[0]/usr/chkBTCH2170-ABORT").selected  = false

' Identitas Job & Rentang Tanggal
session.findById("wnd[0]/usr/txtBTCH2170-JOBNAME").text = "*007b*"
session.findById("wnd[0]/usr/txtBTCH2170-USERNAME").text = "*"
session.findById("wnd[0]/usr/ctxtBTCH2170-FROM_DATE").text = fromDate
session.findById("wnd[0]/usr/ctxtBTCH2170-TO_DATE").text = toDate
session.findById("wnd[0]/usr/ctxtBTCH2170-TO_DATE").setFocus
session.findById("wnd[0]/usr/ctxtBTCH2170-TO_DATE").caretPosition = 2
session.findById("wnd[0]/tbar[1]/btn[8]").press

' Cek apakah grid hasil ditemukan (jika tidak ada job, keluar dengan aman)
On Error Resume Next
rowCount = 0
rowCount = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").RowCount
If Err.Number <> 0 Or rowCount = 0 Then
    session.findById("wnd[0]/tbar[0]/btn[3]").press
    WScript.Quit
End If
On Error GoTo 0

session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").setCurrentCell -1,"STRTDATE"
session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").selectColumn "STRTDATE"
session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").selectColumn "STRTTIME"
session.findById("wnd[0]/tbar[1]/btn[41]").press

' Fungsi untuk mendapatkan kode huruf (A, B, ..., Z, AA, AB, dst)
Function GetPairCode(index)
    Dim code, r
    code = ""
    Dim n
    n = index
    Do
        r = n Mod 26
        code = Chr(65 + r) & code
        n = Int(n / 26) - 1
    Loop While n >= 0
    GetPairCode = code
End Function

If rowCount > 0 Then
    For i = 0 To rowCount - 1
        ' Tentukan Prefix (A, B, C, ...)
        pairIndex = Int(i / 2)
        charPrefix = GetPairCode(pairIndex)
        
        ' Tentukan Suffix (1 atau 2) karena konsepnya berpasangan (A1-A2, B1-B2, etc)
        suffix = (i Mod 2) + 1
        fileName = charPrefix & suffix & ".txt"
        
        ' === Proses Eksekusi GUI (Layar Utama SM37) ===
        session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").currentCellRow = i
        session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").currentCellColumn = "SPOOL_ICON"
        
        ' Buka rincian Spool (ini berpindah layar!)
        session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").doubleClickCurrentCell
        
        ' === Sekarang kita berada di ALV yang baru (Rincian Spool) ===
        ' Pilih kolom RQCOMPIC dan buka Save dialog
        session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").currentCellColumn = "RQCOMPIC"
        session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").clickCurrentCell
        session.findById("wnd[0]/mbar/menu[0]/menu[2]/menu[3]").select
        session.findById("wnd[1]/tbar[0]/btn[0]").press
        
        ' Masukkan Data Path dan Filename
        session.findById("wnd[1]/usr/ctxtDY_PATH").text = savePath
        session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = fileName
        session.findById("wnd[1]/usr/ctxtDY_FILENAME").caretPosition = Len(fileName)
        
        ' Simpan dan kembali 2x ke layar SM37 awal
        session.findById("wnd[1]/tbar[0]/btn[0]").press
        session.findById("wnd[0]/tbar[0]/btn[3]").press
        session.findById("wnd[0]/tbar[0]/btn[3]").press
    Next
End If
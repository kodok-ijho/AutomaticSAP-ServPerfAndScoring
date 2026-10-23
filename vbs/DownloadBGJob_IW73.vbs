' ==============================================================================
' Script: DownloadBGJob_IW73.vbs
' Deskripsi: Otomasi Download Hasil Spool Background Job IW73 via SM37
' Argumen:
'   (0) fromDate   - Tanggal awal filter SM37 (dd.MM.yyyy, misal: 01.10.2026)
'   (1) toDate     - Tanggal akhir filter SM37 (dd.MM.yyyy, misal: 02.10.2026)
'   (2) savePath   - Folder penyimpanan file export (wajib ada trailing \)
'   (3) jobName    - Nama background job di SM37 (default: RIAUFK20)
'   (4) filePrefix - Awalan nama file output (default: IW73_)
' ==============================================================================

Dim fromDate, toDate, savePath, jobName, filePrefix
Dim args
Set args = WScript.Arguments

If args.Count < 3 Then
    WScript.Echo "ERROR: Butuh minimal 3 argumen (fromDate, toDate, savePath)!"
    WScript.Quit 1
End If

fromDate = args(0)
toDate   = args(1)
savePath = args(2)

If args.Count >= 4 Then
    jobName = args(3)
Else
    jobName = "RIAUFK20"
End If

If args.Count >= 5 Then
    filePrefix = args(4)
Else
    filePrefix = "IW73_"
End If

' Pastikan savePath berakhiran backslash
If Right(savePath, 1) <> "\" Then
    savePath = savePath & "\"
End If

On Error Resume Next
Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    WScript.Echo "ERROR: SAP GUI tidak berjalan atau Scripting Engine tidak tersedia."
    WScript.Quit 1
End If

Set application = SapGuiAuto.GetScriptingEngine
If Err.Number <> 0 Or application Is Nothing Then
    WScript.Echo "ERROR: Scripting Engine SAP tidak dapat diinisialisasi."
    WScript.Quit 1
End If

' Cari koneksi dan session yang aktif secara dinamis
Dim activeConn, activeSess, i, j, connCheck, sessCheck, isNewSessionCreated
Set activeConn = Nothing
Set activeSess = Nothing
isNewSessionCreated = False

' 1. Scan semua koneksi dan session untuk menemukan session yang IDLE
For i = 0 To application.Children.Count - 1
    Set connCheck = application.Children(CInt(i))
    For j = 0 To connCheck.Children.Count - 1
        Set sessCheck = connCheck.Children(CInt(j))
        Dim isBusy, tcode
        isBusy = False
        tcode = ""
        On Error Resume Next
        isBusy = sessCheck.Busy
        tcode = UCase(Trim(sessCheck.Info.Transaction))
        On Error GoTo 0
        
        If Not isBusy And (tcode = "SESSION_MANAGER" Or tcode = "S000" Or tcode = "") Then
            Set activeConn = connCheck
            Set activeSess = sessCheck
            WScript.Echo "[VBS] Menggunakan sesi SAP yang tersedia: Sesi (" & j & ") [TCode: " & tcode & "]"
            Exit For
        End If
    Next
    If Not activeSess Is Nothing Then Exit For
Next

' 2. Jika semua session sibuk dan slot masih < 6, buat session baru otomatis
If activeSess Is Nothing And application.Children.Count > 0 Then
    Set connCheck = application.Children(0)
    If connCheck.Children.Count < 6 Then
        WScript.Echo "[VBS] Semua sesi aktif sedang sibuk. Membuat sesi SAP baru..."
        Dim prevCount, waitStep
        prevCount = connCheck.Children.Count
        On Error Resume Next
        connCheck.Children(0).CreateSession
        On Error GoTo 0
        For waitStep = 1 To 20
            WScript.Sleep 500
            If connCheck.Children.Count > prevCount Then
                Set activeConn = connCheck
                Set activeSess = connCheck.Children(connCheck.Children.Count - 1)
                isNewSessionCreated = True
                WScript.Echo "[VBS OK] Berhasil membuat dan terhubung ke sesi SAP baru (Sesi " & (connCheck.Children.Count - 1) & ")"
                Exit For
            End If
        Next
    End If
End If

' Fallback ke Children(0) jika CreateSession tidak tersedia
If activeSess Is Nothing And application.Children.Count > 0 Then
    Set activeConn = application.Children(0)
    If activeConn.Children.Count > 0 Then
        Set activeSess = activeConn.Children(0)
        WScript.Echo "[VBS WARN] Menggunakan sesi fallback (Sesi 0)"
    End If
End If

If activeConn Is Nothing Or activeSess Is Nothing Then
    WScript.Echo "ERROR: Tidak ada session SAP yang dapat digunakan!"
    WScript.Quit 1
End If

Set connection = activeConn
Set session    = activeSess
On Error GoTo 0

If IsObject(WScript) Then
    WScript.ConnectObject session,     "on"
    WScript.ConnectObject application, "on"
End If

session.findById("wnd[0]").maximize

' Dismiss modal popup jika ada dialog terbuka dari sesi sebelumnya
On Error Resume Next
session.findById("wnd[1]/tbar[0]/btn[0]").press
Err.Clear
On Error GoTo 0

' Buka transaksi /nsm37
session.findById("wnd[0]/tbar[0]/okcd").text = "/nsm37"
session.findById("wnd[0]").sendVKey 0
WScript.Sleep 500

' Tunggu layar SM37 siap
Dim loadAttempt, sm37Ready
sm37Ready = False
For loadAttempt = 1 To 10
    On Error Resume Next
    Err.Clear
    session.findById("wnd[1]/tbar[0]/btn[0]").press
    Err.Clear
    session.findById("wnd[0]/usr/txtBTCH2170-JOBNAME").text = jobName
    If Err.Number = 0 Then
        sm37Ready = True
        On Error GoTo 0
        Exit For
    End If
    On Error GoTo 0
    WScript.Sleep 500
Next

' Filter Status: Hanya centang FINISHED
On Error Resume Next
session.findById("wnd[0]/usr/chkBTCH2170-PRELIM").selected = false
session.findById("wnd[0]/usr/chkBTCH2170-SCHED").selected  = false
session.findById("wnd[0]/usr/chkBTCH2170-READY").selected  = false
session.findById("wnd[0]/usr/chkBTCH2170-RUN").selected    = false
session.findById("wnd[0]/usr/chkBTCH2170-FINISH").selected = true
session.findById("wnd[0]/usr/chkBTCH2170-ABORT").selected  = false
Err.Clear
On Error GoTo 0

' Filter Job Name, User, Rentang Tanggal
session.findById("wnd[0]/usr/txtBTCH2170-JOBNAME").text = jobName
session.findById("wnd[0]/usr/txtBTCH2170-USERNAME").text = "*"
session.findById("wnd[0]/usr/ctxtBTCH2170-FROM_DATE").text = fromDate
session.findById("wnd[0]/usr/ctxtBTCH2170-TO_DATE").text = toDate
session.findById("wnd[0]/usr/ctxtBTCH2170-TO_DATE").setFocus

' Jalankan pencarian (F8)
session.findById("wnd[0]/tbar[1]/btn[8]").press
WScript.Sleep 500

' Cek apakah ada job yang ditemukan
Dim rowCount
rowCount = 0
On Error Resume Next
rowCount = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").RowCount
If Err.Number <> 0 Or rowCount = 0 Then
    session.findById("wnd[0]/tbar[0]/btn[3]").press
    WScript.Echo "[VBS INFO] Tidak ada background job FINISHED untuk '" & jobName & "' pada rentang " & fromDate & " s/d " & toDate & "."
    WScript.Quit 0
End If
On Error GoTo 0

WScript.Echo "[VBS] Ditemukan " & rowCount & " background job di SM37. Mengurutkan data..."

' Urutkan grid berdasarkan tanggal & jam mulai secara ascending
session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").setCurrentCell -1, "STRTDATE"
session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").selectColumn "STRTDATE"
session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").selectColumn "STRTTIME"
session.findById("wnd[0]/tbar[1]/btn[41]").press
WScript.Sleep 500

Dim downloadSuccessCount
downloadSuccessCount = 0

For i = 0 To rowCount - 1
    fileName = filePrefix & (i + 1) & ".txt"

    On Error Resume Next
    Err.Clear
    session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").currentCellRow = i
    session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").currentCellColumn = "SPOOL_ICON"

    ' Buka rincian Spool
    session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").doubleClickCurrentCell
    WScript.Sleep 400

    ' Pilih kolom RQCOMPIC dan buka Save dialog (Menu Program -> Save -> Export as Text)
    session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").currentCellColumn = "RQCOMPIC"
    session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").clickCurrentCell
    session.findById("wnd[0]/mbar/menu[0]/menu[2]/menu[3]").select
    WScript.Sleep 300

    ' Pilih Text with tabs (Enter pada popup tipe file)
    session.findById("wnd[1]/tbar[0]/btn[0]").press
    WScript.Sleep 300

    ' Masukkan folder dan nama file
    session.findById("wnd[1]/usr/ctxtDY_PATH").text = savePath
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = fileName
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").caretPosition = Len(fileName)

    ' Tekan Transfer / Generate (Enter)
    session.findById("wnd[1]/tbar[0]/btn[0]").press
    WScript.Sleep 300

    ' Tangani konfirmasi replace jika file sudah ada (wnd[2])
    If session.Children.Count > 2 Then
        session.findById("wnd[2]/tbar[0]/btn[11]").press
        WScript.Sleep 200
    End If

    ' Kembali 2x ke layar SM37
    session.findById("wnd[0]/tbar[0]/btn[3]").press
    session.findById("wnd[0]/tbar[0]/btn[3]").press
    WScript.Sleep 300

    If Err.Number = 0 Then
        downloadSuccessCount = downloadSuccessCount + 1
        WScript.Echo "[VBS OK] Berhasil download spool (" & (i + 1) & "/" & rowCount & "): " & fileName
    Else
        WScript.Echo "[VBS WARN] Gagal download spool baris ke-" & (i + 1) & ": " & Err.Description
        Err.Clear
        ' Coba pastikan kembali ke layar SM37 jika tersangkut
        session.findById("wnd[0]/tbar[0]/btn[3]").press
    End If
    On Error GoTo 0
Next

' Kembali ke layar utama SAP Easy Access atau tutup sesi jika baru dibuat
If isNewSessionCreated Then
    WScript.Echo "[VBS] Menutup sesi SAP sementara yang baru dibuat..."
    On Error Resume Next
    session.findById("wnd[0]").close
    session.findById("wnd[1]/usr/btnSPOP-OPTION1").press
    On Error GoTo 0
Else
    session.findById("wnd[0]/tbar[0]/btn[3]").press
End If

WScript.Echo "OK: Berhasil download " & downloadSuccessCount & " dari " & rowCount & " spool IW73 ke " & savePath
WScript.Quit 0

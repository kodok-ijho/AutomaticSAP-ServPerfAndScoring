' === DownloadZSME09E.vbs ===
' Script otomatisasi download laporan ZSME09E dari SAP GUI
' Argumen yang dibutuhkan:
'   args(0): fromDate (ddMMyy, misal: 270526)
'   args(1): toDate   (ddMMyy, misal: 260626)
'   args(2): savePath (direktori penyimpanan)
'   args(3): fileName (nama file output, misal: ZSME09E_Data_2026-06-01.txt)

On Error Resume Next
Dim SapGuiAuto, application

Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    Err.Clear
    Set SapGuiAuto = CreateObject("Sapgui.ScriptingCtrl.1")
End If

If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    WScript.Echo "[VBS ERROR] SAP GUI tidak tersedia. Buka SAP Logon dan login terlebih dahulu."
    WScript.Quit 1
End If

Set application = SapGuiAuto.GetScriptingEngine
If Err.Number <> 0 Or application Is Nothing Then
    WScript.Echo "[VBS ERROR] Scripting engine SAP tidak dapat diinisialisasi."
    WScript.Quit 1
End If

' Cari koneksi & session aktif
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
    WScript.Echo "[VBS ERROR] Tidak ada session SAP yang aktif. Pastikan SAP sudah login."
    WScript.Quit 1
End If

Set connection = activeConn
Set session = activeSess

If IsObject(WScript) Then
    WScript.ConnectObject session,     "on"
    WScript.ConnectObject application, "on"
End If

' Terima Parameter
Set args = WScript.Arguments
If args.Count < 4 Then
    WScript.Echo "[VBS ERROR] Argumen tidak lengkap! Dibutuhkan 4 argumen: fromDate, toDate, savePath, fileName."
    WScript.Quit 1
End If

fromDate = args(0)
toDate   = args(1)
savePath = args(2)
fileName = args(3)

' Bersihkan trailing backslash dari savePath agar diterima SAP dengan benar
If Right(savePath, 1) = "\" Then
    savePath = Left(savePath, Len(savePath) - 1)
End If

WScript.Echo "[VBS] Parameter diterima: From=" & fromDate & ", To=" & toDate & ", SavePath=" & savePath & ", File=" & fileName

' 1. Dismiss modal popup jika ada dialog terbuka dari sesi sebelumnya
On Error Resume Next
session.findById("wnd[1]/tbar[0]/btn[0]").press
Err.Clear
On Error GoTo 0

' 2. Maximize window utama
On Error Resume Next
session.findById("wnd[0]").maximize
Err.Clear
On Error GoTo 0

' 3. Buka transaksi /nzsme09e
WScript.Echo "[VBS] Membuka transaksi /nzsme09e..."
On Error Resume Next
Err.Clear
session.findById("wnd[0]/tbar[0]/okcd").text = "/nzsme09e"
session.findById("wnd[0]").sendVKey 0
If Err.Number <> 0 Then
    Err.Clear
    session.sendCommand("/nzsme09e")
End If
On Error GoTo 0

' 4. Tunggu sampai layar input ZSME09E siap (maksimal 20x per 500ms = 10 detik)
Dim loadAttempt, screenReady
screenReady = False
For loadAttempt = 1 To 20
    WScript.Sleep 500
    On Error Resume Next
    Err.Clear
    ' Dismiss modal popup jika ada dialog menutup layar
    session.findById("wnd[1]/tbar[0]/btn[0]").press
    Err.Clear

    ' Cek apakah field tanggal From Date sudah ada dan bisa diisi
    session.findById("wnd[0]/usr/ctxtSP$00005-LOW").text = fromDate
    If Err.Number = 0 Then
        screenReady = True
        On Error GoTo 0
        Exit For
    End If
    On Error GoTo 0
Next

If Not screenReady Then
    WScript.Echo "[VBS ERROR] Timeout menunggu layar ZSME09E siap (kontrol ctxtSP$00005-LOW tidak ditemukan)."
    WScript.Quit 1
End If

WScript.Echo "[VBS] Layar ZSME09E siap. Mengisi parameter pencarian..."
On Error Resume Next
Err.Clear
session.findById("wnd[0]/usr/ctxtSP$00005-LOW").text = fromDate
session.findById("wnd[0]/usr/ctxtSP$00005-HIGH").text = toDate
session.findById("wnd[0]/usr/txtSP$00012-LOW").text = ""
session.findById("wnd[0]/usr/ctxtSP$00010-LOW").text = ""
session.findById("wnd[0]/usr/ctxtSP$00010-LOW").setFocus
session.findById("wnd[0]/usr/ctxtSP$00010-LOW").caretPosition = 0
If Err.Number <> 0 Then
    WScript.Echo "[VBS ERROR] Gagal mengisi parameter: " & Err.Description
    WScript.Quit 1
End If
On Error GoTo 0

' 5. Eksekusi Laporan (btn[8])
WScript.Echo "[VBS] Mengeksekusi laporan (Execute / F8)..."
session.findById("wnd[0]/tbar[1]/btn[8]").press

' 6. Tunggu proses pembuatan laporan selesai (polling sampai menu Export Local File tersedia)
WScript.Echo "[VBS] Menunggu hasil laporan ZSME09E selesai diproses SAP..."
Dim reportReady, waitCount
reportReady = False
For waitCount = 1 To 240  ' Maksimal 120 detik (240 x 500ms)
    WScript.Sleep 500
    On Error Resume Next
    Err.Clear

    ' Cek statusbar jika ada pesan peringatan/error seperti "No data selected"
    Dim sbarText, sbarType
    sbarText = session.findById("wnd[0]/sbar").Text
    sbarType = session.findById("wnd[0]/sbar").MessageType
    If sbarType = "E" Then
        WScript.Echo "[VBS SAP ERROR] " & sbarText
        WScript.Quit 1
    ElseIf sbarType = "W" And InStr(LCase(sbarText), "no data") > 0 Then
        WScript.Echo "[VBS SAP WARN] " & sbarText
        WScript.Quit 1
    End If

    ' Coba buka menu Export Local File: List -> Export -> Local File
    session.findById("wnd[0]/mbar/menu[0]/menu[3]/menu[2]").select
    If Err.Number = 0 Then
        reportReady = True
        On Error GoTo 0
        Exit For
    End If
    On Error GoTo 0
Next

If Not reportReady Then
    WScript.Echo "[VBS ERROR] Timeout menunggu hasil laporan ZSME09E atau menu Export tidak dapat diakses."
    WScript.Quit 1
End If

WScript.Echo "[VBS] Menu Export Local File terbuka. Memilih format unconverted..."
' 7. Format Selection Dialog (wnd[1]) -> Tekan Enter untuk format standar (unconverted)
On Error Resume Next
Err.Clear
session.findById("wnd[1]/tbar[0]/btn[0]").press
If Err.Number <> 0 Then
    WScript.Echo "[VBS ERROR] Gagal konfirmasi format export di wnd[1]: " & Err.Description
    WScript.Quit 1
End If
On Error GoTo 0

WScript.Sleep 500

' 8. Dialog Save File (Transfer): masukkan DY_PATH dan DY_FILENAME
WScript.Echo "[VBS] Menyimpan file ke: " & savePath & "\" & fileName & "..."
Dim savedOk
savedOk = False

' Cara 1: Mengisi langsung ke wnd[1] (standar transfer dialog SAP)
On Error Resume Next
Err.Clear
session.findById("wnd[1]/usr/ctxtDY_PATH").text = savePath
session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = fileName
session.findById("wnd[1]/usr/ctxtDY_FILENAME").caretPosition = Len(fileName)
session.findById("wnd[1]/tbar[0]/btn[0]").press  ' Generate / Transfer
If Err.Number = 0 Then
    savedOk = True
    WScript.Echo "[VBS] Perintah transfer file dikirim langsung melalui wnd[1]."
End If
On Error GoTo 0

' Tangani popup konfirmasi overwrite (Replace) jika file sudah ada di folder
On Error Resume Next
session.findById("wnd[1]/usr/btnSPOP-OPTION1").press
session.findById("wnd[2]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[11]").press ' Alternatif tombol Replace
Err.Clear
On Error GoTo 0

' Cara 2 (Fallback): Jika Cara 1 tidak berhasil karena kontrol di wnd[1] berbeda
If Not savedOk Then
    WScript.Echo "[VBS] Mencoba metode alternatif F4 directory browser..."
    On Error Resume Next
    Err.Clear
    session.findById("wnd[1]/usr/ctxtDY_PATH").setFocus
    session.findById("wnd[1]").sendVKey 4
    session.findById("wnd[2]").sendVKey 4
    session.findById("wnd[3]/usr/ctxtDY_PATH").text = savePath
    session.findById("wnd[3]/usr/ctxtDY_FILENAME").text = fileName
    session.findById("wnd[3]/usr/ctxtDY_FILENAME").caretPosition = Len(fileName)
    session.findById("wnd[3]/tbar[0]/btn[0]").press
    session.findById("wnd[2]/tbar[0]/btn[0]").press
    session.findById("wnd[1]/tbar[0]/btn[0]").press
    If Err.Number = 0 Then
        savedOk = True
        WScript.Echo "[VBS] Perintah transfer file dikirim via fallback browser."
    Else
        WScript.Echo "[VBS ERROR] Gagal menyimpan file: " & Err.Description
    End If
    On Error GoTo 0
End If

' Tunggu file selesai ditulis oleh SAP ke disk
WScript.Sleep 1000

' 9. Kembali ke layar utama SAP
On Error Resume Next
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
Err.Clear
On Error GoTo 0

WScript.Echo "[VBS OK] Proses download ZSME09E selesai dieksekusi."
WScript.Quit 0

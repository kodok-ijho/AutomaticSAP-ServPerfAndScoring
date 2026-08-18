Dim Shell, SapGuiAuto, application, connection, session
Set Shell = CreateObject("WScript.Shell")

' ── Helper: Baca nilai dari file .env ──────────────────────────────────────────
Function ReadEnvValue(envFilePath, keyName)
    ReadEnvValue = ""
    Dim fso, ts, line, eqPos
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(envFilePath) Then Exit Function
    Set ts = fso.OpenTextFile(envFilePath, 1, False)
    Do While Not ts.AtEndOfStream
        line = Trim(ts.ReadLine)
        ' Lewati baris kosong dan komentar
        If Len(line) > 0 And Left(line, 1) <> "#" Then
            eqPos = InStr(line, "=")
            If eqPos > 0 Then
                If UCase(Trim(Left(line, eqPos - 1))) = UCase(keyName) Then
                    ReadEnvValue = Mid(line, eqPos + 1)
                    ts.Close
                    Exit Function
                End If
            End If
        End If
    Loop
    ts.Close
End Function

' Tentukan path .env (satu folder di atas vbs/)
Dim envPath
envPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
envPath = Left(envPath, Len(envPath) - 1)  ' hilangkan trailing \
envPath = Left(envPath, InStrRev(envPath, "\")) & ".env"

' Baca kredensial dari .env
Dim envUsername, envPassword, envConnection
envUsername   = ReadEnvValue(envPath, "SAP_USERNAME")
envPassword   = ReadEnvValue(envPath, "SAP_PASSWORD")
envConnection = ReadEnvValue(envPath, "SAP_CONNECTION")

' Fallback ke default jika .env kosong
If envUsername   = "" Then envUsername   = "2436dyu"
If envConnection = "" Then envConnection = "SAP HANA AGDS PROD"

' 1. Cek apakah SAP GUI sudah terbuka
On Error Resume Next
Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Then
    ' SAP GUI belum terbuka, jalankan saplogon.exe
    ' Path standard, silakan sesuaikan jika berbeda
    Shell.Run """C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe"""
    
    ' Tunggu sampai object SAPGUI tersedia
    Do
        WScript.Sleep 1000
        Set SapGuiAuto = GetObject("SAPGUI")
        If Not SapGuiAuto Is Nothing Then Exit Do
    Loop
End If
On Error GoTo 0

Set application = SapGuiAuto.GetScriptingEngine

' 2. Cari koneksi yang sudah memiliki session aktif
Dim foundConnection, foundSession, i
Set foundConnection = Nothing
Set foundSession = Nothing

For i = 0 To application.Children.Count - 1
    Set connCheck = application.Children(CInt(i))
    If connCheck.Children.Count > 0 Then
        Set foundConnection = connCheck
        Set foundSession = connCheck.Children(0)
        Exit For
    End If
Next

If foundConnection Is Nothing Then
    ' Jika tidak ada koneksi dengan session aktif, buka koneksi baru
    On Error Resume Next
    Set connection = application.OpenConnection(envConnection, True) 
    If Err.Number <> 0 Then
        MsgBox "Error: Koneksi SAP dengan nama '" & envConnection & "' tidak ditemukan!" & vbCrLf & vbCrLf & _
               "Penyebab: SAP GUI sudah terbuka di layar 'SAP Logon', tetapi script tidak tahu nama koneksi yang harus dibuka." & vbCrLf & vbCrLf & _
               "Solusi 1: Ubah SAP_CONNECTION di file .env sesuai nama koneksi Anda." & vbCrLf & _
               "Solusi 2: Double-click manual koneksi Anda di SAP Logon sebelum menjalankan script.", vbCritical, "Koneksi SAP Tidak Ditemukan"
        WScript.Quit
    End If
    On Error GoTo 0
    
    ' Tunggu sampai session aktif terbuat (mencegah balapan/race condition)
    ' Timeout diperpanjang ke 60 detik karena koneksi SAP HANA produksi via VPN bisa lambat.
    Dim elapsed
    elapsed = 0
    Do While connection.Children.Count = 0 And elapsed < 120
        WScript.Sleep 500
        elapsed = elapsed + 1
    Loop

    ' Fallback: bila session belum nempel di objek 'connection', pindai ulang
    ' seluruh koneksi siapa tahu session muncul di objek koneksi lain.
    If connection.Children.Count = 0 Then
        Dim j, cc
        For j = 0 To application.Children.Count - 1
            Set cc = application.Children(CInt(j))
            If cc.Children.Count > 0 Then
                Set connection = cc
                Exit For
            End If
        Next
    End If

    If connection.Children.Count = 0 Then
        MsgBox "Error: Koneksi SAP berhasil dibuka, tetapi gagal memuat session baru dalam waktu 60 detik." & vbCrLf & vbCrLf & _
               "Kemungkinan koneksi VPN/SAP sedang lambat. Coba jalankan lagi, atau buka koneksi SAP secara manual lebih dulu.", vbCritical, "Error Session"
        WScript.Quit
    End If

    Set session = connection.Children(CInt(0))
Else
    Set connection = foundConnection
    Set session = foundSession
End If

' 4. Lakukan Login jika di layar login
' Cek apakah field username ada
On Error Resume Next
Set usrField = session.findById("wnd[0]/usr/txtRSYST-BNAME")
If Err.Number = 0 Then
    ' Kita di layar login — isi username dari .env
    usrField.text = envUsername
    
    ' Isi password dari .env
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = envPassword
    
    ' Jika password tersedia dari .env, otomatis tekan Enter untuk login
    If Len(envPassword) > 0 And envPassword <> "********" Then
        session.findById("wnd[0]").sendVKey 0
        WScript.Sleep 2000
        ' Jika ada popup multi-login (License Information), tekan Enter
        On Error Resume Next
        session.findById("wnd[1]").sendVKey 0
        On Error GoTo 0
    End If
End If
On Error GoTo 0

' 5. TUNGGU SAMPAI BENAR-BENAR LOGIN
' Script akan pause di sini sampai layar login (field username) hilang
On Error Resume Next
Do
    Err.Clear
    Set checkLogin = session.findById("wnd[0]/usr/txtRSYST-BNAME")
    If Err.Number <> 0 Then 
        ' Error artinya field username sudah tidak ditemukan -> sudah berhasil login!
        Exit Do
    End If
    WScript.Sleep 1000
Loop
On Error GoTo 0

' Selesai login, session siap digunakan
session.findById("wnd[0]").maximize

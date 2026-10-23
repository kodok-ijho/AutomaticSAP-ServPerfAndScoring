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

' Tentukan path .env
Dim envPath
envPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
envPath = Left(envPath, Len(envPath) - 1)
envPath = Left(envPath, InStrRev(envPath, "\")) & ".env"

Dim envUsername, envPassword, envConnection
envUsername   = ReadEnvValue(envPath, "SAP_USERNAME")
envPassword   = ReadEnvValue(envPath, "SAP_PASSWORD")
envConnection = ReadEnvValue(envPath, "SAP_CONNECTION")

If envUsername   = "" Then envUsername   = "2436dyu"
If envConnection = "" Then envConnection = "SAP HANA AGDS PROD"

' ── STEP 1: Cek apakah SAP session sudah aktif via GetObject ─────────────────
Dim waitCount, sapOk
sapOk = False

On Error Resume Next
Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number = 0 And Not SapGuiAuto Is Nothing Then
    ' SAP Logon sudah terbuka — cek apakah ada koneksi aktif
    Set application = SapGuiAuto.GetScriptingEngine
    If Err.Number = 0 And application.Children.Count > 0 Then
        Dim connCheck
        Set connCheck = application.Children(0)
        If connCheck.Children.Count > 0 Then
            sapOk = True  ' Ada session aktif, tidak perlu buka baru
        End If
    End If
End If
Err.Clear
On Error GoTo 0

' ── STEP 2: Jika belum ada session, gunakan sapshcut.exe untuk buka koneksi langsung ──
If Not sapOk Then
    Dim sapshcut
    sapshcut = "C:\Program Files (x86)\SAP\FrontEnd\SapGui\sapshcut.exe"

    ' sapshcut.exe membuka koneksi SAP langsung dengan user+password otomatis
    Shell.Run """" & sapshcut & """ -system=""" & envConnection & """ -user=""" & envUsername & """ -pw=""" & envPassword & """ -language=EN", 1, False
    WScript.Sleep 3000

    ' Polling sampai GetObject("SAPGUI") berhasil dan ada session (maks 45 detik)
    For waitCount = 1 To 45
        On Error Resume Next
        Err.Clear
        Set SapGuiAuto = GetObject("SAPGUI")
        If Err.Number = 0 And Not SapGuiAuto Is Nothing Then
            Set application = SapGuiAuto.GetScriptingEngine
            If Err.Number = 0 And application.Children.Count > 0 Then
                Set connCheck = application.Children(0)
                If connCheck.Children.Count > 0 Then
                    sapOk = True
                    Exit For
                End If
            End If
        End If
        On Error GoTo 0
        WScript.Sleep 1000
    Next
    On Error GoTo 0
End If

If Not sapOk Then
    WScript.Echo "ERROR: Tidak dapat membuka session SAP setelah 45 detik."
    WScript.Quit 1
End If

' ── STEP 3: Ambil / cari session aktif ───────────────────────────────────────
If Not IsObject(application) Or application Is Nothing Then
    Set application = SapGuiAuto.GetScriptingEngine
End If

Dim foundConnection, foundSession, i
Set foundConnection = Nothing
Set foundSession    = Nothing

For i = 0 To application.Children.Count - 1
    Dim conn
    Set conn = application.Children(CInt(i))
    If conn.Children.Count > 0 Then
        Set foundConnection = conn
        Set foundSession    = conn.Children(0)
        Exit For
    End If
Next

If foundConnection Is Nothing Or foundSession Is Nothing Then
    WScript.Echo "ERROR: Tidak ada session SAP aktif."
    WScript.Quit 1
End If

Set connection = foundConnection
Set session    = foundSession

' ── STEP 4: Login jika masih di layar login ──────────────────────────────────
On Error Resume Next
Err.Clear
Dim usrField
Set usrField = session.findById("wnd[0]/usr/txtRSYST-BNAME")
If Err.Number = 0 And Not usrField Is Nothing Then
    usrField.text = envUsername
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = envPassword
    If Len(envPassword) > 0 Then
        session.findById("wnd[0]").sendVKey 0
        WScript.Sleep 2500
        ' Dismiss multi-login / system message popup jika ada
        Err.Clear
        session.findById("wnd[1]/tbar[0]/btn[0]").press
        If Err.Number <> 0 Then
            Err.Clear
            session.findById("wnd[1]").sendVKey 0
        End If
    End If
End If
Err.Clear
On Error GoTo 0

' ── STEP 5: Tunggu sampai benar-benar login (maks 30 detik) ──────────────────
Dim chkWait
For chkWait = 1 To 30
    On Error Resume Next
    Err.Clear
    session.findById("wnd[0]/usr/txtRSYST-BNAME")
    If Err.Number <> 0 Then
        ' Field login sudah hilang -> login berhasil
        Exit For
    End If
    WScript.Sleep 1000
Next

On Error Resume Next
session.findById("wnd[0]").maximize
On Error GoTo 0

WScript.Quit 0

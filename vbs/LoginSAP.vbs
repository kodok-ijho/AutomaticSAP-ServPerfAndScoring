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

' ── STEP 1: Cek apakah SAP GUI sudah berjalan atau jalankan saplogon.exe ───
Dim waitCount, sapOk
sapOk = False

On Error Resume Next
Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    Err.Clear
    Shell.Run """C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe""", 1, False
    For waitCount = 1 To 20
        WScript.Sleep 1000
        Err.Clear
        Set SapGuiAuto = GetObject("SAPGUI")
        If Err.Number = 0 And Not SapGuiAuto Is Nothing Then Exit For
    Next
End If

If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    Err.Clear
    Set SapGuiAuto = CreateObject("Sapgui.ScriptingCtrl.1")
End If

If Err.Number = 0 And Not SapGuiAuto Is Nothing Then
    Set application = SapGuiAuto.GetScriptingEngine
    If Err.Number = 0 And Not application Is Nothing Then
        If application.Children.Count > 0 Then
            Dim connCheck
            Set connCheck = application.Children(0)
            If connCheck.Children.Count > 0 Then
                sapOk = True  ' Ada session aktif
            End If
        End If
    End If
End If
Err.Clear
On Error GoTo 0

' ── STEP 2: Jika belum ada session, buka koneksi via OpenConnection ──────────
If Not sapOk Then
    On Error Resume Next
    If Not application Is Nothing Then
        Set connection = application.OpenConnection(envConnection, True)
        WScript.Sleep 2500
        If Err.Number = 0 And Not connection Is Nothing Then
            If connection.Children.Count > 0 Then
                sapOk = True
            End If
        End If
    End If
    Err.Clear
    On Error GoTo 0
End If

If Not sapOk Then
    WScript.Echo "ERROR: Tidak dapat membuka session SAP untuk '" & envConnection & "'."
    WScript.Quit 1
End If

' ── STEP 3: Ambil session aktif ──────────────────────────────────────────────
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
        
        ' Cek pesan error di status bar setelah menekan Enter
        Dim sbarMsg, sbarType
        sbarMsg = session.findById("wnd[0]/sbar").Text
        sbarType = session.findById("wnd[0]/sbar").MessageType
        If sbarType = "E" Or sbarType = "A" Then
            WScript.Echo "ERROR SAP LOGIN: [" & sbarType & "] " & sbarMsg
            WScript.Quit 1
        End If

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
    
    ' Pantau status bar jika muncul pesan error
    sbarMsg = session.findById("wnd[0]/sbar").Text
    sbarType = session.findById("wnd[0]/sbar").MessageType
    If sbarType = "E" Or sbarType = "A" Then
        WScript.Echo "ERROR SAP LOGIN: [" & sbarType & "] " & sbarMsg
        WScript.Quit 1
    End If
    
    WScript.Sleep 1000
Next

' Verifikasi final: pastikan sudah tidak di layar login
On Error Resume Next
Err.Clear
session.findById("wnd[0]/usr/txtRSYST-BNAME")
If Err.Number = 0 Then
    sbarMsg = session.findById("wnd[0]/sbar").Text
    sbarType = session.findById("wnd[0]/sbar").MessageType
    WScript.Echo "ERROR: Masih berada di layar login SAP. Pesan: " & sbarMsg
    WScript.Quit 1
End If

session.findById("wnd[0]").maximize
On Error GoTo 0

WScript.Echo "SUCCESS: Login SAP berhasil."
WScript.Quit 0

' ==============================================================================
' Script: IW58-per 5 hari.vbs
' Deskripsi: Otomasi Penjadwalan Background Job IW58 di SAP GUI
' Argumen:
'   (0) startDate  - Tanggal filter awal (ddMMyy, misal: 010126)
'   (1) endDate    - Tanggal filter akhir (ddMMyy, misal: 050126)
'   (2) schedDate  - Tanggal eksekusi BG Job di SAP (ddMMyy, misal: 021026)
'   (3) schedTime  - Jam eksekusi BG Job di SAP (HHmm, misal: 1745)
' ==============================================================================

Dim startDate, endDate, schedDate, schedTime
Dim args
Set args = WScript.Arguments

If args.Count >= 4 Then
    startDate  = args(0)
    endDate    = args(1)
    schedDate  = args(2)
    schedTime  = args(3)
Else
    ' Fallback jika dijalankan manual tanpa argumen (nilai rekaman asli)
    startDate  = "010116"
    endDate    = "050116"
    schedDate  = "021026"
    schedTime  = "1745"
End If

On Error Resume Next
Set SapGuiAuto  = GetObject("SAPGUI")
If Err.Number <> 0 Or SapGuiAuto Is Nothing Then
    WScript.Echo "ERROR: SAP GUI tidak berjalan atau Scripting Engine tidak tersedia."
    WScript.Quit 1
End If

Set application = SapGuiAuto.GetScriptingEngine
If Err.Number <> 0 Or application Is Nothing Then
    WScript.Echo "ERROR: Scripting Engine SAP tidak dapat diinisialisasi."
    WScript.Quit 1
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
On Error GoTo 0

If IsObject(WScript) Then
    WScript.ConnectObject session,     "on"
    WScript.ConnectObject application, "on"
End If

' Navigasi ke transaksi IW58
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nIW58"
session.findById("wnd[0]").sendVKey 0

' Centang opsi Outstanding & In Process
session.findById("wnd[0]/usr/chkDY_RST").selected = true
session.findById("wnd[0]/usr/chkDY_MAB").selected = true

' Isi rentang tanggal DATUV dan DATUB
session.findById("wnd[0]/usr/ctxtDATUV").text = startDate
session.findById("wnd[0]/usr/ctxtDATUB").text = endDate
session.findById("wnd[0]/usr/ctxtDATUB").setFocus
session.findById("wnd[0]/usr/ctxtDATUB").caretPosition = Len(endDate)
session.findById("wnd[0]").sendVKey 0

' Pilih Variant sesuai rekaman asli
session.findById("wnd[0]/usr/ctxtVARIANT").setFocus
session.findById("wnd[0]/usr/ctxtVARIANT").caretPosition = 0
session.findById("wnd[0]").sendVKey 4
session.findById("wnd[1]/usr").verticalScrollbar.position = 10
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/16[0,16]/lbl[1,16]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/16[0,16]/lbl[1,16]").caretPosition = 6
session.findById("wnd[1]").sendVKey 2

' Menu Program -> Execute in Background (F9)
session.findById("wnd[0]/mbar/menu[0]/menu[2]").select
session.findById("wnd[1]/tbar[0]/btn[13]").press
session.findById("wnd[1]/usr/btnDATE_PUSH").press

' Atur tanggal dan jam eksekusi Background Job
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTDT").text = schedDate
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").text = schedTime
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").setFocus
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").caretPosition = 4

' Check, Save, dan Kembali
session.findById("wnd[1]").sendVKey 0
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[11]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press

WScript.Echo "OK: Berhasil menjadwalkan IW58 (" & startDate & " - " & endDate & ") pada " & schedDate & " pukul " & schedTime
WScript.Quit 0

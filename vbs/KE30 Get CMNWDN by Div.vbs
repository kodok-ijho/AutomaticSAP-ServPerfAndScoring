On Error Resume Next
If Not IsObject(application) Then
   Set SapGuiAuto  = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
If Not IsObject(connection) Then
   Set connection = application.Children(0)
End If
If Not IsObject(session) Then
   Set session    = connection.Children(0)
End If
If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If
Dim targetYear, targetMonth, saveFolder
targetYear = "2026"
targetMonth = "06"
saveFolder = "D:\Kerja\2026 CSSD\03. KE30\KE30 - 06 JUN 26\AUTO\BY DIV"

If WScript.Arguments.Count >= 1 Then
   If WScript.Arguments(0) <> "" Then targetYear = WScript.Arguments(0)
End If
If WScript.Arguments.Count >= 2 Then
   If WScript.Arguments(1) <> "" Then targetMonth = WScript.Arguments(1)
End If
If WScript.Arguments.Count >= 3 Then
   If WScript.Arguments(2) <> "" Then saveFolder = WScript.Arguments(2)
End If

If Right(saveFolder, 1) = "\" Then
   saveFolder = Left(saveFolder, Len(saveFolder) - 1)
End If

Dim periodTag, todayTag, d, m, y
periodTag = Right("0" & targetMonth, 2) & Right(targetYear, 2)
d = Right("0" & Day(Date), 2)
m = Right("0" & Month(Date), 2)
y = Right(Year(Date), 2)
todayTag = d & m & y

' Helper untuk memilih baris pada modal dialog wnd[1] dengan proteksi auto-scroll
Sub SelectDivRow(rowIndex, caret)
    On Error Resume Next
    Err.Clear
    session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/" & rowIndex & "[0," & rowIndex & "]/lbl[1," & rowIndex & "]").setFocus
    If Err.Number <> 0 Then
        ' Jika kontrol belum kelihatan di viewport modal window, scroll tabel ke bawah
        Err.Clear
        Dim scrollPos
        scrollPos = rowIndex - 18
        If scrollPos < 1 Then scrollPos = 1
        session.findById("wnd[1]/usr").verticalScrollbar.position = scrollPos
        session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/" & rowIndex & "[0," & rowIndex & "]/lbl[1," & rowIndex & "]").setFocus
    End If
    session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/" & rowIndex & "[0," & rowIndex & "]/lbl[1," & rowIndex & "]").caretPosition = caret
    session.findById("wnd[1]").sendVKey 2
    On Error GoTo 0
End Sub

Sub DownloadDivFile(divCode)
    session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
    session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - " & periodTag & " - " & todayTag & " - " & divCode & ".dat"
    session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
    session.findById("wnd[1]/tbar[0]/btn[0]").press
End Sub

Sub OpenDivPicker()
    session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
    session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
    session.findById("wnd[0]").sendVKey 2
End Sub

session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nke30"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/shellcont/shell").selectedNode = "000000001044"
session.findById("wnd[0]/tbar[1]/btn[8]").press
session.findById("wnd[0]/usr/ctxtPAR_01").text = targetYear
session.findById("wnd[0]/usr/ctxtPAR_05").text = targetMonth
session.findById("wnd[0]/usr/ctxtPAR_05").setFocus
session.findById("wnd[0]/usr/ctxtPAR_05").caretPosition = 2
session.findById("wnd[0]/tbar[1]/btn[8]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[1,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[1,8]").caretPosition = 5
session.findById("wnd[0]").sendVKey 2

' Divisi 11 (Save path via dialog konfigurasi awal)
OpenDivPicker
SelectDivRow 5, 1
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]").sendVKey 4
session.findById("wnd[2]/usr/ctxtDY_PATH").setFocus
session.findById("wnd[2]/usr/ctxtDY_PATH").caretPosition = 0
session.findById("wnd[2]").sendVKey 4
session.findById("wnd[3]/usr/ctxtDY_PATH").setFocus
session.findById("wnd[3]/usr/ctxtDY_PATH").caretPosition = 0
session.findById("wnd[3]").sendVKey 4
session.findById("wnd[4]/usr/ctxtDY_PATH").setFocus
session.findById("wnd[4]/usr/ctxtDY_PATH").caretPosition = 0
session.findById("wnd[4]").sendVKey 4
session.findById("wnd[5]/usr/ctxtDY_PATH").text = saveFolder
session.findById("wnd[5]/usr/ctxtDY_FILENAME").text = "KE30 CMNWDN - " & periodTag & " - " & todayTag & " - 11.dat"
session.findById("wnd[5]/usr/ctxtDY_FILENAME").caretPosition = 22
session.findById("wnd[5]/tbar[0]/btn[0]").press
session.findById("wnd[4]/tbar[0]/btn[0]").press
session.findById("wnd[3]/tbar[0]/btn[0]").press
session.findById("wnd[2]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[0]").press

' Divisi 12 s/d 72
OpenDivPicker: SelectDivRow 6, 1: DownloadDivFile "12"
OpenDivPicker: SelectDivRow 8, 0: DownloadDivFile "16"
OpenDivPicker: SelectDivRow 9, 1: DownloadDivFile "21"
OpenDivPicker: SelectDivRow 10, 1: DownloadDivFile "22"
OpenDivPicker: SelectDivRow 11, 0: DownloadDivFile "23"
OpenDivPicker: SelectDivRow 12, 1: DownloadDivFile "24"
OpenDivPicker: SelectDivRow 13, 0: DownloadDivFile "25"
OpenDivPicker: SelectDivRow 14, 1: DownloadDivFile "26"
OpenDivPicker: SelectDivRow 15, 0: DownloadDivFile "27"
OpenDivPicker: SelectDivRow 16, 0: DownloadDivFile "31"
OpenDivPicker: SelectDivRow 17, 1: DownloadDivFile "32"
OpenDivPicker: SelectDivRow 18, 0: DownloadDivFile "33"
OpenDivPicker: SelectDivRow 19, 2: DownloadDivFile "41"
OpenDivPicker: SelectDivRow 20, 2: DownloadDivFile "42"
OpenDivPicker: SelectDivRow 21, 1: DownloadDivFile "43"
OpenDivPicker: SelectDivRow 22, 1: DownloadDivFile "44"
OpenDivPicker: SelectDivRow 23, 1: DownloadDivFile "45"
OpenDivPicker: SelectDivRow 24, 1: DownloadDivFile "46"
OpenDivPicker: SelectDivRow 25, 1: DownloadDivFile "47"
OpenDivPicker: SelectDivRow 26, 0: DownloadDivFile "48"
OpenDivPicker: SelectDivRow 29, 1: DownloadDivFile "61"
OpenDivPicker: SelectDivRow 30, 0: DownloadDivFile "62"
OpenDivPicker: SelectDivRow 31, 1: DownloadDivFile "71"
OpenDivPicker: SelectDivRow 32, 1: DownloadDivFile "72"

' Transisi ke Tampilan View 2
session.findById("wnd[0]/mbar/menu[0]/menu[12]").select
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[1]/usr/btnBUTTON_1").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[1,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[1,8]").caretPosition = 5
session.findById("wnd[0]").sendVKey 2

' Divisi 81 & 82
OpenDivPicker: SelectDivRow 33, 0: DownloadDivFile "81"
OpenDivPicker: SelectDivRow 34, 1: DownloadDivFile "82"

' Divisi 83 (Scroll 4)
OpenDivPicker
session.findById("wnd[1]/usr").verticalScrollbar.position = 4
SelectDivRow 31, 0
DownloadDivFile "83"

' Divisi 84 (Scroll 2)
OpenDivPicker
session.findById("wnd[1]/usr").verticalScrollbar.position = 2
SelectDivRow 34, 0
DownloadDivFile "84"

' Divisi 91 (Scroll 4)
OpenDivPicker
session.findById("wnd[1]/usr").verticalScrollbar.position = 4
SelectDivRow 33, 2
DownloadDivFile "91"

' Kembali ke Easy Access Menu
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[1]/usr/btnSPOP-OPTION1").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press

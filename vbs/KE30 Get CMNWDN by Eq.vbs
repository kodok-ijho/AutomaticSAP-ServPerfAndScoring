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
Dim saveFolder, periodTag, fullFilePath, targetMonth, targetYear
saveFolder = "D:\Kerja\2026 CSSD\03. KE30\KE30 - 07 JUL 26"
periodTag = "0726"

If WScript.Arguments.Count >= 1 Then
   If WScript.Arguments(0) <> "" Then periodTag = WScript.Arguments(0)
End If
If WScript.Arguments.Count >= 2 Then
   If WScript.Arguments(1) <> "" Then saveFolder = WScript.Arguments(1)
End If

If Right(saveFolder, 1) = "\" Then
   saveFolder = Left(saveFolder, Len(saveFolder) - 1)
End If

targetMonth = Left(periodTag, 2)
targetYear = "20" & Right(periodTag, 2)

fullFilePath = saveFolder & "\KE30 by EQ - " & periodTag & ".dat"

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
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[22,11]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[22,11]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[1,9]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[1,9]").caretPosition = 12
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[26,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[26,8]").caretPosition = 9
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/2[0,0]/lbl[1,12]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/2[0,0]/lbl[1,12]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[42,14]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[42,14]").caretPosition = 0
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[42,14]").showContextMenu
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[42,14]").caretPosition = 118
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]").sendVKey 38
session.findById("wnd[1]/tbar[0]/btn[6]").press
session.findById("wnd[1]/usr").verticalScrollbar.position = 252
session.findById("wnd[1]/usr/sub:SAPLKYP1:0100/chkSEL_TABLE-CHOICE[8,0]").selected = true
session.findById("wnd[1]/usr/sub:SAPLKYP1:0100/chkSEL_TABLE-CHOICE[8,0]").setFocus
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/btnD2000_PUSH_03").press
session.findById("wnd[1]").sendVKey 4
session.findById("wnd[2]/usr/ctxtDY_PATH").text = saveFolder & "\"
session.findById("wnd[2]/usr/ctxtDY_FILENAME").text = "KE30 by EQ - " & periodTag
session.findById("wnd[2]/usr/ctxtDY_FILENAME").caretPosition = 17
session.findById("wnd[2]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[2]/tbar[0]/btn[0]").press
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = fullFilePath
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 66
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[1]/usr/btnSPOP-OPTION1").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press

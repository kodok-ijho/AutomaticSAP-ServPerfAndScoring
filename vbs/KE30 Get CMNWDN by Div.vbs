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
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/5[0,5]/lbl[1,5]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/5[0,5]/lbl[1,5]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
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
session.findById("wnd[5]/usr/ctxtDY_FILENAME").text = "KE30 CMNWDN - 0626 - 300626 - 11.dat"
session.findById("wnd[5]/usr/ctxtDY_FILENAME").caretPosition = 22
session.findById("wnd[5]/tbar[0]/btn[0]").press
session.findById("wnd[4]/tbar[0]/btn[0]").press
session.findById("wnd[3]/tbar[0]/btn[0]").press
session.findById("wnd[2]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/6[0,6]/lbl[1,6]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/6[0,6]/lbl[1,6]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 12.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/8[0,8]/lbl[1,8]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/8[0,8]/lbl[1,8]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 16.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/9[0,9]/lbl[1,9]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/9[0,9]/lbl[1,9]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 21.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]").sendVKey 0
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/10[0,10]/lbl[1,10]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/10[0,10]/lbl[1,10]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 22.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]").sendVKey 0
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/11[0,11]/lbl[1,11]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/11[0,11]/lbl[1,11]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 23.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/12[0,12]/lbl[1,12]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/12[0,12]/lbl[1,12]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 24.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/13[0,13]/lbl[1,13]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/13[0,13]/lbl[1,13]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 25.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/14[0,14]/lbl[1,14]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/14[0,14]/lbl[1,14]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 26.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/15[0,15]/lbl[1,15]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/15[0,15]/lbl[1,15]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 27.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/16[0,16]/lbl[1,16]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/16[0,16]/lbl[1,16]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 31.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/17[0,17]/lbl[1,17]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/17[0,17]/lbl[1,17]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 32.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/18[0,18]/lbl[1,18]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/18[0,18]/lbl[1,18]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 33.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/19[0,19]/lbl[1,19]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/19[0,19]/lbl[1,19]").caretPosition = 2
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 41.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/20[0,20]/lbl[1,20]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/20[0,20]/lbl[1,20]").caretPosition = 2
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 42.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/21[0,21]/lbl[1,21]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/21[0,21]/lbl[1,21]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 43.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/22[0,22]/lbl[1,22]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/22[0,22]/lbl[1,22]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 44.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/23[0,23]/lbl[1,23]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/23[0,23]/lbl[1,23]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 45.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/24[0,24]/lbl[1,24]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/24[0,24]/lbl[1,24]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 46.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/25[0,25]/lbl[1,25]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/25[0,25]/lbl[1,25]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 47.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/26[0,26]/lbl[1,26]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/26[0,26]/lbl[1,26]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 48.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/29[0,29]/lbl[1,29]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/29[0,29]/lbl[1,29]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 61.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/30[0,30]/lbl[1,30]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/30[0,30]/lbl[1,30]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 62.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/31[0,31]/lbl[1,31]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/31[0,31]/lbl[1,31]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 71.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/32[0,32]/lbl[1,32]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/32[0,32]/lbl[1,32]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 72.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/33[0,33]/lbl[1,33]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/33[0,33]/lbl[1,33]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[12]").select
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[1]/usr/btnBUTTON_1").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[1,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[1,8]").caretPosition = 5
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/33[0,33]/lbl[1,33]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/33[0,33]/lbl[1,33]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 81.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/34[0,34]/lbl[1,34]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/34[0,34]/lbl[1,34]").caretPosition = 1
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 82.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr").verticalScrollbar.position = 4
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/31[0,31]/lbl[1,31]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/31[0,31]/lbl[1,31]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 83.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr").verticalScrollbar.position = 1
session.findById("wnd[1]/usr").verticalScrollbar.position = 2
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/34[0,34]/lbl[1,34]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/34[0,34]/lbl[1,34]").caretPosition = 0
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 84.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").setFocus
session.findById("wnd[0]/usr/sub/1[0,0]/sub/1/4[0,7]/lbl[50,8]").caretPosition = 0
session.findById("wnd[0]").sendVKey 2
session.findById("wnd[1]/usr").verticalScrollbar.position = 1
session.findById("wnd[1]/usr").verticalScrollbar.position = 2
session.findById("wnd[1]/usr").verticalScrollbar.position = 3
session.findById("wnd[1]/usr").verticalScrollbar.position = 4
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/33[0,33]/lbl[1,33]").setFocus
session.findById("wnd[1]/usr/sub/1[0,0]/sub/1/2[0,0]/sub/1/2/33[0,33]/lbl[1,33]").caretPosition = 2
session.findById("wnd[1]").sendVKey 2
session.findById("wnd[0]/mbar/menu[0]/menu[11]").select
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").text = saveFolder & "\KE30 CMNWDN - 0626 - 300626 - 91.dat"
session.findById("wnd[1]/usr/ctxtCFDOWNLOAD-FILE").caretPosition = 89
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[1]/usr/btnSPOP-OPTION1").press
session.findById("wnd[0]/tbar[0]/btn[3]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press

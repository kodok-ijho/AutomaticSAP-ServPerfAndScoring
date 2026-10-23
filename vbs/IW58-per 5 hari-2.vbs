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
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "IW58"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/chkDY_RST").selected = true
session.findById("wnd[0]/usr/chkDY_MAB").selected = true
session.findById("wnd[0]/usr/ctxtDATUV").text = "010116"
session.findById("wnd[0]/usr/ctxtDATUB").text = "050116"
session.findById("wnd[0]/usr/ctxtDATUB").setFocus
session.findById("wnd[0]/usr/ctxtDATUB").caretPosition = 6
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]").sendVKey 9
session.findById("wnd[1]/tbar[0]/btn[13]").press
session.findById("wnd[1]/usr/btnDATE_PUSH").press
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTDT").text = "021026"
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").text = "1745"
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").setFocus
session.findById("wnd[1]/usr/ctxtBTCH1010-SDLSTRTTM").caretPosition = 4
session.findById("wnd[1]").sendVKey 0
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[1]/tbar[0]/btn[11]").press
session.findById("wnd[0]/tbar[0]/btn[3]").press

import os, sys, win32com.client

src = os.path.abspath(sys.argv[1])
out = os.path.abspath(sys.argv[2])

app = win32com.client.Dispatch("PowerPoint.Application")
pres = app.Presentations.Open(src, WithWindow=False)
pres.SaveAs(out, 32)  # 32 = ppSaveAsPDF
pres.Close()
app.Quit()
print("saved", out)

import os, sys, win32com.client

src = os.path.abspath(sys.argv[1])
out_dir = os.path.abspath(sys.argv[2])
os.makedirs(out_dir, exist_ok=True)

app = win32com.client.Dispatch("PowerPoint.Application")
pres = app.Presentations.Open(src, WithWindow=False)
pres.Export(out_dir, "PNG", 1600, 900)
pres.Close()
app.Quit()
print("exported to", out_dir)

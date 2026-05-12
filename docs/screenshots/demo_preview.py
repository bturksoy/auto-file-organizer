"""Launch the app with a sample folder and run a Preview automatically.

Used to generate the README screenshots. Picks the language from the saved
settings, so re-running this after switching languages produces a localized
screenshot.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Users\Burhan\file-organizer")
import tkinter as tk
from organizer import OrganizerApp, load_settings

sample_root = Path(tempfile.mkdtemp(prefix="fo_demo_"))
sample_files = [
    "Jane_CV_2024.pdf",
    "AcmeCV_Doe.docx",
    "Fatura-2024-03.pdf",
    "BORDRO_2024_07.pdf",
    "Bank_dekont.pdf",
    "Mietvertrag_apartment.pdf",
    "Ibraname.pdf",
    "Visum Letter.pdf",
    "vodafonenumaratasima.pdf",
    "biletmart.pdf",
    "ehliyet_belgesi.pdf",
    "IPV Antrag_Signed.pdf",
    "Protokoll Theorie (1).pdf",
    "VMwareKullaniciKilavuzu.pdf",
    "vacation.mp4",
    "song.mp3",
    "photo.jpg",
    "archive.zip",
    "main.py",
    "Screenshot 2024-01-15.png",
    "Setup_Chrome.exe",
    "report.docx",
    "028-random-id.pdf",
]
for name in sample_files:
    (sample_root / name).write_bytes(b"x")

settings = load_settings()
root = tk.Tk()
app = OrganizerApp(root, settings)
app.folder_var.set(str(sample_root))
app.verbose_var.set(False)
root.after(200, app._preview)
root.geometry("920x660")
root.mainloop()

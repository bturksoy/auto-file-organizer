"""
Launches OrganizerApp with a sample folder pre-set and Preview already run,
so we can capture a screenshot showing the categorization output.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Burhan\file-organizer")
import tkinter as tk
from organizer import OrganizerApp

# Build a sample folder with files that exercise multiple categories.
sample_root = Path(tempfile.mkdtemp(prefix="fo_demo_"))
sample_files = [
    "Burhan_CV_2024.pdf",
    "LinkteraCV_AyseDemir.docx",
    "Fatura-2024-03.pdf",
    "BURHAN_TURKSOY_BORDRO.pdf",
    "Enpara.com dekontunuz.pdf",
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
    "rapor.docx",
    "028-random-id.pdf",
]
for n in sample_files:
    (sample_root / n).write_bytes(b"x")

root = tk.Tk()
app = OrganizerApp(root)
app.folder_var.set(str(sample_root))
app.verbose_var.set(False)
# Trigger preview immediately (next tick so the app is fully constructed)
root.after(200, app._preview)
# Resize a bit for nicer screenshot
root.geometry("900x640")
root.mainloop()

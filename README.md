# Auto File Organizer

A standalone Windows utility that scans a folder and automatically sorts files
into category subfolders. Built specifically to tame messy Downloads folders.

No installation, no setup, no dependencies — just one `.exe`.

![Main window](docs/screenshots/main-window.png)

## Highlights

- **Single-file `.exe`** — download and run. No installer, no Python, no admin rights.
- **Three-layer classification**
  - Filename pattern matching across **20+ categories**
  - **PDF/DOCX content inspection** — detects CVs even when the filename gives no hint
  - Fallback to extension-based grouping for common file types
- **Multilingual** — works on Turkish, English, and German filenames out of the box
- **Smart Turkish handling** — folds dotless `ı → i`, strips combining marks
  (so `Kılavuz` matches `kilavuz`, `EHLİYET` matches `ehliyet`)
- **Fuzzy match for broken PDFs** — when a PDF's font has missing Unicode mappings
  (common with Canva/Figma exports) the keywords are still found via single-character
  edit-distance variants
- **Preview before you commit** — see exactly what will move where, then confirm
- **Full undo** — every operation is reversible. Logs are kept per-folder
- **Diagnostic mode** — toggle "Tanı detayları" to see *why* each file was
  classified the way it was

## Preview in action

Run **Önizle** to see the categorization plan before any file is touched:

![Preview output](docs/screenshots/preview-demo.png)

## Categories

| Category | Trigger source | Examples of what it catches |
|---|---|---|
| **CV** | name + PDF/DOCX content | `Burhan_CV_2024.pdf`, `LinkteraCV_Ayse.docx`, `Resume.pdf`, content with "Curriculum Vitae" / "Özgeçmiş" / "Work Experience + Education + Skills" |
| **Faturalar** | name | `Fatura`, `invoice`, `receipt`, `makbuz`, `bill` |
| **Bordro** | name | `bordro`, `gehaltsabrechnung`, `turnusabrechnung`, `payslip`, `payroll` |
| **Banka** | name | `dekont`, `kontoauszug`, `payment confirmation`, `transaction details`, `account statement`, `risk merkez`, `varlik degisim` |
| **Vergi** | name | `steuerberater`, `mandanteninformation`, `finanzamt`, `vergi beyanname` |
| **Telekom** | name | `vodafone`, `turkcell`, `turk telekom`, `numara tasima` |
| **Sigorta** | name | `sigorta`, `versicherung`, `sfr ausland`, `ipv antrag` |
| **Sözleşme** | name | `sözleşme`, `mietvertrag`, `vertragsbestätigung`, `zusatzvereinbarung`, `kündigung`, `vollmacht`, `ibraname`, `mitgliedschaft`, `ek protokol` |
| **Konut** | name | `mietspiegel`, `yapi raporu`, `zemin yapi`, `tapu`, `emlak`, `nebenkostenabrechnung` |
| **Bilet** | name | `bilet`, `ticket`, `boarding pass` (substring) |
| **Vize** | name | `visum`, `einladungsschreiben`, `antragszusammenfassung` |
| **Resmi Belge** | name | `dijital kimlik`, `nvi-`, `emniyet-`, `ehliyet`, `pasaport`, `mezun belgesi`, `oturum uzat`, `sicil kayd`, `e-devlet` |
| **Sınav** | name | `protokoll theorie`, `ergebnisprotokoll` |
| **Kılavuz** | name | `kılavuz`, `user guide`, `manual`, `handbuch` |
| **İade** | name | `iade`, `refund`, `return label` |
| **Loglar** | name | `eventlog`, `errorlog`, `crashlog` |
| **Araç** | name | `pdf-expose-`, `piaggio`, `limousine`, `bmw_`, `mercedes_`, `audi_`, `vw_`, `renault_` |
| **Ekran Görüntüleri** | name | `screenshot`, `screen shot`, `ekran goruntusu`, `screencap` |
| **Kurulum** | name + ext | filename starts with `setup_`/`installer_` or has `.exe`/`.msi`/`.msix` |
| **Belgeler** | ext | `.pdf`, `.doc`, `.docx`, `.txt`, `.rtf`, `.odt`, `.md`, `.epub`, ... |
| **Tablolar** | ext | `.xls`, `.xlsx`, `.csv`, `.ods` |
| **Sunumlar** | ext | `.ppt`, `.pptx`, `.odp`, `.key` |
| **Resimler** | ext | `.jpg`, `.png`, `.gif`, `.webp`, `.heic`, `.svg`, ... |
| **Videolar** | ext | `.mp4`, `.avi`, `.mkv`, `.mov`, ... |
| **Müzik** | ext | `.mp3`, `.wav`, `.flac`, `.aac`, `.m4a`, ... |
| **Arşivler** | ext | `.zip`, `.rar`, `.7z`, `.tar.gz`, ... |
| **Kod** | ext | `.py`, `.js`, `.ts`, `.html`, `.cpp`, `.cs`, `.gd`, ... |
| **Yazı Tipleri** | ext | `.ttf`, `.otf`, `.woff`, `.woff2` |
| **Disk Kalıbı** | ext | `.iso`, `.img`, `.dmg`, `.vhd` |
| **Torrent** | ext | `.torrent` |
| **Diğer** | fallback | anything not matched above |

## How it works

Classification is a 4-step waterfall — first match wins:

1. **CamelCase CV check** on the original filename (catches `LinkteraCV_*`,
   `UfukYucelCv_2025.pdf` etc. that strict word-boundary rules miss)
2. **Name patterns** on the normalized filename (lowercased, NFD-decomposed,
   combining marks stripped, dotless `ı` folded to `i`)
3. **Content inspection** for `.pdf` and `.docx` — extracts text from the first
   3-4 pages, normalizes, then looks for:
   - **Strong CV signals** (1 hit ⇒ CV): `curriculum vitae`, `özgeçmiş`, `resume`, `résumé`
   - **Weak CV signals** (2+ hits ⇒ CV): `work experience`, `education`, `skills`,
     `certifications`, `references`, `languages`, `iş deneyimi`, `eğitim`,
     `yetenekler`, `sertifikalar`, `kişisel bilgiler`, `linkedin.com/in/`, etc.
   - **Fuzzy fallback** if exact matching fails: drops one internal character
     from each keyword and re-checks against whitespace-stripped text. This
     recovers CVs from PDFs where a font's glyph-to-Unicode mapping is broken
     and individual characters (often `i`) are silently dropped.
4. **Extension** lookup against the category map above.

Files that don't match anything land in `Diğer`. Subfolders are never touched —
only the chosen folder's top-level files. Name collisions get `(1)`, `(2)`
suffixes so nothing is ever overwritten.

## Install

1. Grab `FileOrganizer.exe` from the [latest release](../../releases/latest).
2. Double-click. There is no installer.

The file is roughly 27 MB (bundles Python 3.13, tkinter, pypdf, python-docx via
PyInstaller `--onefile`). First launch unpacks once into your temp directory
and is slightly slower than subsequent runs — this is normal.

## Use

1. Click **Gözat...** and pick a folder (e.g. your Downloads).
2. Click **Önizle** to see how files will be grouped. Nothing moves yet.
   - Optionally tick **Tanı detayları** to see *why* each file was put where.
3. Click **Düzenle** and confirm. Files move into category subfolders inside
   the chosen folder.
4. **Geri Al** undoes the most recent operation. The undo history is kept in
   `.file-organizer-undo.json` in that folder.

## Safety notes

- The app only touches files at the **top level** of the chosen folder.
  Existing subfolders (including ones the app created previously) are ignored.
- Files are **moved**, not copied. Use Geri Al to put them back.
- Conflicts get a `(1)`, `(2)`, ... suffix — nothing is overwritten.
- Scanned PDFs and image-only PDFs have no extractable text, so CV detection
  by content cannot work on them. Their filename signal is still used. If
  you want them in `CV`, rename them to include `_cv_` (or move them manually).
- Encrypted PDFs are silently skipped (treated as `Belgeler` by extension).

## Build from source

Prerequisites: Python 3.10+ on Windows.

```powershell
git clone https://github.com/bturksoy/auto-file-organizer.git
cd auto-file-organizer
.\build.ps1
```

Output: `dist\FileOrganizer.exe`

## Stack

- **Python 3.13** with **tkinter** for the UI (no extra GUI framework)
- **pypdf** for PDF text extraction
- **python-docx** for Word document parsing
- **PyInstaller** to produce the single-file `.exe`

The entire app is a single `organizer.py` source file (~400 lines).

## License

MIT — see [LICENSE](LICENSE).

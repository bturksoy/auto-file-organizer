"""
Dosya Düzenleyici — Windows klasör organizasyon aracı.
Kurulum gerektirmez; PyInstaller ile tek dosya exe olarak paketlenir.
"""
import functools
import json
import logging
import queue
import re
import shutil
import threading
import tkinter as tk
import unicodedata
from datetime import datetime
from pathlib import Path
from tkinter import END, filedialog, messagebox, ttk

APP_TITLE = "Dosya Düzenleyici"
UNDO_LOG_NAME = ".file-organizer-undo.json"

# pypdf bozuk PDF'ler için bol uyarı basıyor; --windowed modunda konsol yok
# ama yine de stderr'i kirletiyor. Kapat.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def _normalize(s: str) -> str:
    """
    Türkçe büyük/küçük harf ve aksan farkını yok say.
    'ÖZGEÇMİŞ', 'özgeçmiş', 'ozgecmis' → hepsi 'ozgecmis' olur.
    Önemli kararlar:
    - Python'un 'İ'.lower() 'i + U+0307 combining dot' üretir; NFD + Mn
      strip ile combining dot'u sileriz ('İ' → 'i').
    - Türkçe dotless 'ı' (U+0131) standalone bir harf, NFD onu çözmez;
      bu yüzden 'i'ye katlamak için açıkça replace ediyoruz.
      ('Kılavuz' → 'kilavuz' böylece 'kilavuz' anahtar kelimesiyle eşleşir.)
    """
    s = unicodedata.normalize("NFD", s.casefold())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("ı", "i")


def _maybe_despace(text: str) -> str:
    """
    Bazı PDF'ler (Canva, Figma, vs. ile yapılmış) her harfi ayrı text
    objesi olarak render eder; pypdf de aralarına boşluk koyar:
    "W o r k  E x p e r i e n c e"
    Bunu tespit edip toparlıyoruz. Eğer token'ların %40+'sı tek harfse,
    tek boşlukları (harfler arası) silip çift boşlukları (kelimeler arası)
    tek boşluğa indiriyoruz.
    """
    tokens = text.split()
    if len(tokens) < 10:
        return text
    single_char_ratio = sum(1 for t in tokens if len(t) == 1) / len(tokens)
    if single_char_ratio < 0.4:
        return text
    # Çift+ boşlukları placeholder ile koru, tek boşlukları sil, geri al.
    out = re.sub(r"  +", "\x00", text)
    out = out.replace(" ", "")
    return out.replace("\x00", " ")


# CV içerik tespiti için anahtar kelimeler. _normalize'a benziyor;
# karşılaştırma sırasında her ikisi de normalize edilir.
_CV_STRONG_RAW = (
    "curriculum vitae",
    "özgeçmiş",
    "resume",
    "résumé",
)

_CV_WEAK_RAW = (
    # English başlıklar
    "work experience", "professional experience", "employment history",
    "education", "academic background", "educational background",
    "skills", "technical skills", "soft skills", "core competencies",
    "references", "professional references",
    "certificates", "certifications", "certification", "certified",
    "career objective", "professional summary", "personal summary",
    "contact information", "contact details",
    "languages", "language proficiency", "language skills",
    "personal information", "personal details", "personal profile",
    "projects", "publications",
    "date of birth", "place of birth", "nationality",
    "hobbies", "interests",
    "linkedin.com/in/", "github.com/",
    # Türkçe başlıklar
    "iş deneyimi", "çalışma deneyimi", "iş tecrübesi", "iş hayatı",
    "deneyim", "tecrübe",
    "eğitim", "eğitim bilgileri", "öğrenim", "öğrenim durumu",
    "yetenekler", "yetkinlikler", "beceriler", "yetkinlik",
    "referanslar", "referans",
    "sertifikalar", "sertifika", "sertifikalarım",
    "kişisel bilgiler", "iletişim bilgileri", "iletişim",
    "diller", "yabancı dil", "yabancı diller", "dil bilgisi",
    "projeler", "yayınlar",
    "kariyer hedefi", "kariyer", "kariyer özeti",
    "doğum tarihi", "doğum yeri", "uyruğu", "medeni durum",
    "hobiler", "ilgi alanları", "ilgi alanlarım",
    "hakkımda", "özet", "profil",
)

_CV_STRONG = tuple(_normalize(kw) for kw in _CV_STRONG_RAW)
_CV_WEAK = tuple(_normalize(kw) for kw in _CV_WEAK_RAW)


def _read_pdf_text(path: Path, max_pages: int = 4) -> str:
    """İlk birkaç sayfadan metin çıkar. Hata olursa boş döner."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            return ""
        chunks = []
        for page in reader.pages[:max_pages]:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(chunks)
    except Exception:
        return ""


def _read_docx_text(path: Path) -> str:
    """Word .docx dosyasından metin çıkar."""
    try:
        from docx import Document
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs if p.text]
        # Tabloları da topla (CV'lerde çok kullanılır)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        parts.append(cell.text)
        return "\n".join(parts)
    except Exception:
        return ""


@functools.lru_cache(maxsize=1024)
def _read_pdf_text_cached(path_str: str, mtime: float, size: int) -> str:
    return _read_pdf_text(Path(path_str))


@functools.lru_cache(maxsize=1024)
def _read_docx_text_cached(path_str: str, mtime: float, size: int) -> str:
    return _read_docx_text(Path(path_str))


def _aggressive_strip(s: str) -> str:
    """Tüm whitespace + null/control byte'ları sil. Fuzzy karşılaştırma için."""
    return re.sub(r"[\s\x00-\x1f]+", "", s)


def _kw_variants_drop_one(kw_agg: str):
    """
    Anahtar kelimenin iç karakterlerinden birini düşürerek varyantlar üret.
    Bazı PDF'lerde belirli bir glyph (örn. 'i') unicode'a map edilmediği için
    metinden o karakter kaybolur ('Education' -> 'Educat on' -> 'Educaton').
    Bu varyantlar o tür kırık metinleri yakalar.
    """
    if len(kw_agg) < 6:
        return  # çok kısa, yanlış pozitif riski yüksek
    for i in range(1, len(kw_agg) - 1):  # ilk ve son karakteri koru
        yield kw_agg[:i] + kw_agg[i + 1:]


def cv_signals(text: str):
    """
    Metinden CV sinyallerini bul. (strong_hits, weak_hits) listelerini döner.
    Önce exact match (normalize edilmiş metin üzerinde),
    yetersizse fuzzy fallback (her kelimenin tek-harf-eksik varyantları,
    tüm whitespace strip'lenmiş metin üzerinde).
    """
    if not text:
        return [], []
    text = _maybe_despace(text)
    t = _normalize(text)
    strong = [kw for kw in _CV_STRONG if kw in t]
    weak = [kw for kw in _CV_WEAK if kw in t]

    # Yeterli sinyal varsa fuzzy'e gerek yok
    if strong or len(weak) >= 2:
        return strong, weak

    # Fuzzy fallback
    t_agg = _aggressive_strip(t)
    if len(t_agg) < 50:
        return strong, weak  # çok az metin, fuzzy güvenilmez

    for kw in _CV_STRONG:
        if kw in strong:
            continue
        kw_agg = _aggressive_strip(kw)
        for variant in _kw_variants_drop_one(kw_agg):
            if variant in t_agg:
                strong.append(kw + " (~)")
                break
    for kw in _CV_WEAK:
        if kw in weak:
            continue
        kw_agg = _aggressive_strip(kw)
        for variant in _kw_variants_drop_one(kw_agg):
            if variant in t_agg:
                weak.append(kw + " (~)")
                break
    return strong, weak


def looks_like_cv(text: str) -> bool:
    strong, weak = cv_signals(text)
    return bool(strong) or len(weak) >= 2

# İsim eşleştirmesi normalize-form (lowercase + NFD + Mn-strip) üzerinde yapılır.
# Bu sayede 'ÖZGEÇMİŞ', 'özgeçmiş', 'ozgecmis' → 'ozgecmis' olur ve tek pattern yeter.
# Sözcük sınırı: tireleme/altçizgi/boşluk/nokta saymak için harf-olmayan sınır.
_LB = r"(?<![a-z0-9])"
_RB = r"(?![a-z0-9])"

# CamelCase CV: 'LinkteraCV_', 'UfukYucelCv-2025'. Orijinal isim (case-sensitive)
# üzerinde çalışır: küçük harf + büyük 'CV'/'Cv' + ayraç veya son.
_CAMELCASE_CV = re.compile(r"(?<=[a-z])(CV|Cv)(?=[_\-\s.]|$)")

NAME_RULES = [
    # CV — kelime sınırlı (2 harf, false positive riski yüksek)
    (re.compile(_LB + r"(cv|resume|ozgecmis)" + _RB), "CV"),

    # Faturalar
    (re.compile(_LB + r"(fatura|invoice|receipt|fis|makbuz|bill)" + _RB), "Faturalar"),

    # Ekran Görüntüleri
    (re.compile(
        r"(screenshot|screen[\s_-]?shot|ekran[\s_-]?goruntusu|screencap)"
    ), "Ekran Görüntüleri"),

    # Kurulum
    (re.compile(r"^(setup|installer|install)[\s_\-.]"), "Kurulum"),

    # Bordro / Maaş
    (re.compile(
        r"(bordro|gehaltsabrechnung|lohnabrechnung|turnusabrechnung|payslip|payroll)"
    ), "Bordro"),

    # Banka / Dekont
    (re.compile(
        r"(dekont|"
        r"kontoauszug|"
        r"payment[\s_-]+confirmation|"
        r"transaction[\s_-]+details|"
        r"account[\s_-]+statement|"
        r"risk[\s_-]?merkez|"
        r"varlik[\s_-]?degisim)"
    ), "Banka"),

    # Vergi / Steuer
    (re.compile(
        r"(steuerberater|"
        r"mandanteninformation|"
        r"finanzamt|"
        r"steuererklarung|"
        r"vergi[\s_-]+(?:levha|beyanname|beyani|dairesi))"
    ), "Vergi"),

    # Telekom
    (re.compile(
        r"(vodafone|"
        r"turkcell|"
        r"turk[\s_-]?telekom|"
        r"numara[\s_-]?tasima)"
    ), "Telekom"),

    # Sigorta — Vize'den önce gelmeli ('ipv antrag' buraya aittir)
    (re.compile(
        r"(sigorta|"
        r"versicherung|"
        r"sfr[\s_-]+ausland|"
        r"ipv[\s_-]?antrag)"
    ), "Sigorta"),

    # Sözleşme
    (re.compile(
        r"(sozlesme|"
        r"mietvertrag|"
        r"vertragsbestatigung|"
        r"zusatzvereinbarung|"
        r"kundigung|"
        r"vollmacht|"
        r"ibraname|"
        r"mitgliedschaft|"
        r"ek[\s_-]+protokol)"
    ), "Sözleşme"),

    # Konut / Emlak
    (re.compile(
        r"(mietspiegel|"
        r"yapi[\s_-]?raporu|"
        r"zemin[\s_-]?yapi|"
        r"nebenkostenabrechnung|"
        r"emlak|"
        r"(?<![a-z0-9])tapu(?![a-z0-9]))"
    ), "Konut"),

    # Bilet (sub-string match — 'btbilet', 'biletmart' yakalansın diye)
    (re.compile(r"(bilet|ticket|boarding[\s_-]?pass)"), "Bilet"),

    # Vize (IPV çıkarıldı, Sigorta'ya gitti)
    (re.compile(
        r"(visum|"
        r"einladungsschreiben|"
        r"antragszusammenfassung)"
    ), "Vize"),

    # Resmi Belge
    (re.compile(
        r"(dijital[\s_-]?kimlik|"
        r"nvi[\s_-]|"
        r"emniyet[\s_-]|"
        r"ehliyet|"
        r"pasaport|"
        r"mezun[\s_-]?belgesi|"
        r"oturum[\s_-]?uzat|"
        r"sicil[\s_-]?kayd|"
        r"e[\s_-]?devlet)"
    ), "Resmi Belge"),

    # Sınav
    (re.compile(
        r"(protokoll[\s_-]+theorie|ergebnisprotokoll)"
    ), "Sınav"),

    # Kılavuz / Manual
    (re.compile(
        r"(kilavuz|user[\s_-]?guide|handbuch|"
        r"(?<![a-z0-9])manual(?![a-z0-9]))"
    ), "Kılavuz"),

    # İade
    (re.compile(
        r"(?<![a-z0-9])(?:iade|refund)(?![a-z0-9])|return[\s_-]+label"
    ), "İade"),

    # Loglar — gerçek log dosyaları (genelde silinebilir)
    (re.compile(
        r"(eventlog|errorlog|crashlog|debuglog|"
        r"event[\s_-]+log|error[\s_-]+log|crash[\s_-]+log)"
    ), "Loglar"),

    # Araç / Expose
    (re.compile(
        r"(pdf-?expose-|"
        r"piaggio|"
        r"\blimousine\b|"
        r"(?:^|[\s_\-.])(?:bmw|mercedes|audi|vw|volkswagen|renault)[\s_\-])"
    ), "Araç"),
]

EXT_CATEGORIES = {
    "Belgeler": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".tex",
                 ".epub", ".mobi", ".azw3", ".pages"},
    "Tablolar": {".xls", ".xlsx", ".csv", ".ods", ".tsv", ".numbers"},
    "Sunumlar": {".ppt", ".pptx", ".odp", ".key"},
    "Resimler": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif",
                 ".svg", ".heic", ".ico", ".psd", ".ai", ".raw", ".cr2", ".nef"},
    "Videolar": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v",
                 ".mpg", ".mpeg", ".3gp"},
    "Müzik": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus", ".aiff"},
    "Arşivler": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"},
    "Kurulum": {".exe", ".msi", ".msix", ".appx", ".appxbundle"},
    "Kod": {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css", ".scss",
            ".java", ".kt", ".cpp", ".c", ".h", ".hpp", ".cs", ".go", ".rs", ".rb",
            ".php", ".swift", ".sh", ".ps1", ".bat", ".cmd", ".json", ".xml",
            ".yml", ".yaml", ".toml", ".ini", ".sql", ".lua", ".gd"},
    "Yazı Tipleri": {".ttf", ".otf", ".woff", ".woff2"},
    "Disk Kalıbı": {".iso", ".img", ".dmg", ".vhd", ".vmdk"},
    "Torrent": {".torrent"},
}

OTHER = "Diğer"
ALL_CATEGORIES = set(EXT_CATEGORIES.keys()) | {c for _, c in NAME_RULES} | {OTHER}
SKIP_NAMES = {UNDO_LOG_NAME, "desktop.ini", "Thumbs.db", "thumbs.db", "$RECYCLE.BIN"}


def classify_detailed(filepath: Path, inspect_content: bool = True):
    """
    Sınıflandırma + tanı bilgisi.
    Döner: (category, reason)
      reason: insanlara okutmak için kısa açıklama
    """
    name = filepath.name
    # CamelCase CV (orijinal isim, case-sensitive)
    m = _CAMELCASE_CV.search(name)
    if m:
        return "CV", f"isim: CamelCase '{m.group()}'"
    # Geri kalan kurallar normalize edilmiş isim üzerinde
    name_norm = _normalize(name)
    for pattern, category in NAME_RULES:
        m = pattern.search(name_norm)
        if m:
            return category, f"isim: '{m.group()}'"
    ext = filepath.suffix.lower()

    if inspect_content and ext in (".pdf", ".docx"):
        try:
            st = filepath.stat()
            if ext == ".pdf":
                text = _read_pdf_text_cached(str(filepath), st.st_mtime, st.st_size)
                src = "PDF"
            else:
                text = _read_docx_text_cached(str(filepath), st.st_mtime, st.st_size)
                src = "DOCX"
        except OSError:
            text, src = "", ext.upper()
        strong, weak = cv_signals(text)
        if strong:
            return "CV", f"{src} içerik güçlü: {', '.join(strong[:3])}"
        if len(weak) >= 2:
            return "CV", f"{src} içerik zayıf×{len(weak)}: {', '.join(weak[:4])}"
        # CV değil — ama metin durumunu belirt
        if not text:
            content_note = f"{src} metin yok (taranmış/şifreli olabilir)"
        elif weak:
            content_note = f"{src} CV değil (zayıf×{len(weak)}: {', '.join(weak[:3])})"
        else:
            content_note = f"{src} CV değil ({len(text)} kr metin, eşleşme yok)"
        # Uzantıya geri düş
        for category, exts in EXT_CATEGORIES.items():
            if ext in exts:
                return category, f"uzantı {ext} ({content_note})"
        return OTHER, f"uzantı eşleşmedi ({content_note})"

    for category, exts in EXT_CATEGORIES.items():
        if ext in exts:
            return category, f"uzantı {ext}"
    return OTHER, f"uzantı eşleşmedi: {ext}"


def classify(filepath: Path, inspect_content: bool = True) -> str:
    return classify_detailed(filepath, inspect_content)[0]


def plan_moves(root: Path, progress_cb=None, with_reason: bool = False):
    """
    progress_cb(i, total, current_filename) — opsiyonel.
    with_reason=True ise tuple (src, dst, category, reason) döner.
    """
    entries = []
    for entry in root.iterdir():
        if entry.is_dir():
            continue
        if entry.name in SKIP_NAMES or entry.name.startswith("."):
            continue
        entries.append(entry)
    moves = []
    total = len(entries)
    for i, entry in enumerate(entries, 1):
        if progress_cb:
            progress_cb(i, total, entry.name)
        category, reason = classify_detailed(entry)
        if with_reason:
            moves.append((entry, root / category / entry.name, category, reason))
        else:
            moves.append((entry, root / category / entry.name, category))
    return moves


def resolve_conflict(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem, suffix, parent = dst.stem, dst.suffix, dst.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


class OrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("820x580")
        self.root.minsize(640, 480)

        self.folder_var = tk.StringVar()
        self.verbose_var = tk.BooleanVar(value=False)
        self.msg_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()

        self._build_ui()
        self.root.after(100, self._drain_queue)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Klasör:").pack(side="left")
        ttk.Entry(top, textvariable=self.folder_var).pack(
            side="left", fill="x", expand=True, padx=(6, 6)
        )
        ttk.Button(top, text="Gözat...", command=self._browse).pack(side="left")

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)
        self.preview_btn = ttk.Button(btns, text="Önizle", command=self._preview)
        self.preview_btn.pack(side="left", padx=(0, 6))
        self.organize_btn = ttk.Button(btns, text="Düzenle", command=self._organize)
        self.organize_btn.pack(side="left", padx=(0, 6))
        self.undo_btn = ttk.Button(btns, text="Geri Al", command=self._undo)
        self.undo_btn.pack(side="left", padx=(0, 6))
        ttk.Checkbutton(
            btns, text="Tanı detayları", variable=self.verbose_var
        ).pack(side="left", padx=(12, 0))
        ttk.Button(btns, text="Logu Temizle", command=self._clear_log).pack(side="right")

        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill="x", **pad)

        self.status_var = tk.StringVar(value="Hazır.")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(
            fill="x", padx=10
        )

        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, wrap="none", font=("Consolas", 9))
        yscroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        xscroll = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log.xview)
        self.log.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

    def _browse(self):
        folder = filedialog.askdirectory(title="Düzenlenecek klasörü seç")
        if folder:
            self.folder_var.set(folder)

    def _log(self, msg):
        self.log.insert(END, msg + "\n")
        self.log.see(END)

    def _clear_log(self):
        self.log.delete("1.0", END)

    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.preview_btn.config(state=state)
        self.organize_btn.config(state=state)
        self.undo_btn.config(state=state)

    def _get_root(self):
        path = self.folder_var.get().strip().strip('"')
        if not path:
            messagebox.showwarning(APP_TITLE, "Önce bir klasör seç.")
            return None
        root = Path(path)
        if not root.is_dir():
            messagebox.showerror(APP_TITLE, f"Klasör bulunamadı:\n{path}")
            return None
        return root

    def _preview(self):
        root = self._get_root()
        if not root:
            return
        self._clear_log()
        self._log(f"=== Önizleme: {root} ===")
        self._log("(PDF & Word dosyaları CV tespiti için içeriden taranıyor...)\n")
        self._set_busy(True)
        verbose = self.verbose_var.get()
        threading.Thread(
            target=self._preview_worker, args=(root, verbose), daemon=True
        ).start()

    def _preview_worker(self, root: Path, verbose: bool):
        def progress_cb(i, total, name):
            self.msg_queue.put(("progress_max", total))
            self.msg_queue.put(("progress", i))
            self.msg_queue.put(("status", f"İnceleniyor {i}/{total}: {name}"))
        try:
            moves = plan_moves(root, progress_cb=progress_cb, with_reason=True)
            if not moves:
                self.msg_queue.put(("log", "Düzenlenecek dosya yok."))
                self.msg_queue.put(("done", "Boş."))
                return
            by_cat = {}
            for src, _dst, cat, reason in moves:
                by_cat.setdefault(cat, []).append((src.name, reason))
            for cat in sorted(by_cat):
                self.msg_queue.put(("log", f"[{cat}]  ({len(by_cat[cat])} dosya)"))
                for name, reason in sorted(by_cat[cat]):
                    if verbose:
                        self.msg_queue.put(("log", f"  - {name}    [{reason}]"))
                    else:
                        self.msg_queue.put(("log", f"  - {name}"))
                self.msg_queue.put(("log", ""))
            self.msg_queue.put((
                "log", f"Toplam: {len(moves)} dosya, {len(by_cat)} kategori."
            ))
            if not verbose:
                self.msg_queue.put((
                    "log",
                    "İpucu: Bir dosya yanlış kategoride mi? 'Tanı detayları'nı aç ve tekrar Önizle.",
                ))
            self.msg_queue.put(("done", f"Önizleme: {len(moves)} dosya hazır."))
        except Exception as e:
            self.msg_queue.put(("log", f"\nFATAL HATA: {e}"))
            self.msg_queue.put(("done", "Hata."))

    def _organize(self):
        root = self._get_root()
        if not root:
            return
        if not messagebox.askyesno(
            APP_TITLE,
            f"{root}\n\nİçindeki dosyalar kategori klasörlerine taşınacak. Devam edilsin mi?",
        ):
            return
        self._set_busy(True)
        threading.Thread(target=self._organize_worker, args=(root,), daemon=True).start()

    def _organize_worker(self, root: Path):
        try:
            moves = plan_moves(root)
            self.msg_queue.put(("log", f"=== Düzenleniyor: {root} ==="))
            if not moves:
                self.msg_queue.put(("log", "Düzenlenecek dosya yok."))
                self.msg_queue.put(("done", "Boş."))
                return
            self.msg_queue.put(("progress_max", len(moves)))
            undo_entries = []
            errors = 0
            ts = datetime.now().isoformat(timespec="seconds")
            for i, (src, dst, cat) in enumerate(moves, 1):
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    final_dst = resolve_conflict(dst)
                    shutil.move(str(src), str(final_dst))
                    undo_entries.append({"from": str(final_dst), "to": str(src)})
                    self.msg_queue.put(("log", f"[{cat}] {src.name}"))
                except Exception as e:
                    errors += 1
                    self.msg_queue.put(("log", f"HATA: {src.name} -> {e}"))
                self.msg_queue.put(("progress", i))
            undo_path = root / UNDO_LOG_NAME
            history = []
            if undo_path.exists():
                try:
                    history = json.loads(undo_path.read_text(encoding="utf-8"))
                except Exception:
                    history = []
            history.append({"timestamp": ts, "moves": undo_entries})
            try:
                undo_path.write_text(
                    json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception as e:
                self.msg_queue.put(("log", f"UYARI: Geri-al kütüğü yazılamadı: {e}"))
            self.msg_queue.put((
                "log",
                f"\nBitti. {len(undo_entries)} dosya taşındı, {errors} hata.",
            ))
            self.msg_queue.put(("done", f"Tamam: {len(undo_entries)} taşındı, {errors} hata."))
        except Exception as e:
            self.msg_queue.put(("log", f"\nFATAL HATA: {e}"))
            self.msg_queue.put(("done", "Hata."))

    def _undo(self):
        root = self._get_root()
        if not root:
            return
        undo_path = root / UNDO_LOG_NAME
        if not undo_path.exists():
            messagebox.showinfo(APP_TITLE, "Geri alınacak işlem bulunamadı.")
            return
        try:
            history = json.loads(undo_path.read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Geri-al kütüğü okunamadı:\n{e}")
            return
        if not history:
            messagebox.showinfo(APP_TITLE, "Geri alınacak işlem bulunamadı.")
            return
        last = history[-1]
        n = len(last["moves"])
        if not messagebox.askyesno(
            APP_TITLE,
            f"Son işlem geri alınacak: {n} dosya, {last['timestamp']} tarihinde taşınmıştı.\nDevam edilsin mi?",
        ):
            return
        self._set_busy(True)
        threading.Thread(
            target=self._undo_worker, args=(root, history), daemon=True
        ).start()

    def _undo_worker(self, root: Path, history):
        try:
            last = history.pop()
            self.msg_queue.put(("log", f"=== Geri alınıyor: {last['timestamp']} ==="))
            moves = last["moves"]
            self.msg_queue.put(("progress_max", len(moves)))
            errors = 0
            for i, m in enumerate(reversed(moves), 1):
                src, dst = Path(m["from"]), Path(m["to"])
                try:
                    if src.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        final_dst = resolve_conflict(dst)
                        shutil.move(str(src), str(final_dst))
                        self.msg_queue.put(("log", f"<- {final_dst.name}"))
                    else:
                        self.msg_queue.put(("log", f"ATLANDI (kayıp): {src.name}"))
                except Exception as e:
                    errors += 1
                    self.msg_queue.put(("log", f"HATA: {src} -> {e}"))
                self.msg_queue.put(("progress", i))
            for cat in ALL_CATEGORIES:
                d = root / cat
                if d.is_dir():
                    try:
                        if not any(d.iterdir()):
                            d.rmdir()
                    except Exception:
                        pass
            undo_path = root / UNDO_LOG_NAME
            if history:
                undo_path.write_text(
                    json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            else:
                try:
                    undo_path.unlink()
                except Exception:
                    pass
            self.msg_queue.put((
                "log",
                f"\nGeri alma bitti. {len(moves) - errors} dosya, {errors} hata.",
            ))
            self.msg_queue.put(("done", "Geri alındı."))
        except Exception as e:
            self.msg_queue.put(("log", f"\nFATAL HATA: {e}"))
            self.msg_queue.put(("done", "Hata."))

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "progress_max":
                    self.progress.config(maximum=payload, value=0)
                elif kind == "progress":
                    self.progress.config(value=payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "done":
                    self.status_var.set(payload)
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    OrganizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""File Organizer — sort a folder's files into category subfolders.

Single-file Tk application. Categorization combines filename patterns with
optional PDF/DOCX text inspection for CV detection. Built to be packaged as a
standalone Windows executable via PyInstaller --onefile.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import queue
import re
import shutil
import sys
import threading
import tkinter as tk
import unicodedata
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import END, filedialog, messagebox, ttk

APP_NAME = "File Organizer"
APP_VERSION = "1.1.0"
UNDO_LOG_NAME = ".file-organizer-undo.json"
BMC_URL = "https://buymeacoffee.com/bturksoy"
DEFAULT_LANG = "en"

# pypdf is noisy about malformed streams. We don't want to crash on it.
logging.getLogger("pypdf").setLevel(logging.ERROR)


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------

def _config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "FileOrganizer" / "settings.json"


def load_settings() -> dict:
    path = _config_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(data: dict) -> None:
    path = _config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # If we can't write settings, the app should still run.
        pass


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGES = {"en": "English", "tr": "Türkçe"}

UI_STRINGS = {
    "en": {
        "app_title": "File Organizer",
        "folder_label": "Folder:",
        "browse_btn": "Browse...",
        "preview_btn": "Preview",
        "organize_btn": "Organize",
        "undo_btn": "Undo",
        "verbose_check": "Diagnostic details",
        "clear_log_btn": "Clear log",
        "status_ready": "Ready.",
        "menu_file": "File",
        "menu_exit": "Exit",
        "menu_settings": "Settings",
        "menu_preferences": "Preferences...",
        "menu_help": "Help",
        "menu_about": "About",
        "settings_title": "Preferences",
        "settings_language": "Language:",
        "settings_save": "Save",
        "settings_cancel": "Cancel",
        "settings_restart_note": "Language change takes effect immediately.",
        "about_title": "About",
        "about_body": (
            "{app} v{ver}\n\nA standalone file organizer.\n"
            "Single .exe, no installation."
        ),
        "bmc_label": "Support the project",
        "pick_folder_first": "Pick a folder first.",
        "folder_not_found": "Folder not found:\n{path}",
        "confirm_organize": (
            "{path}\n\nFiles in this folder will be moved into category "
            "subfolders. Continue?"
        ),
        "confirm_undo": (
            "The last operation moved {n} file(s) on {date}. Undo it?"
        ),
        "preview_header": "=== Preview: {path} ===",
        "preview_scanning": (
            "(Scanning PDF and Word documents for CV content...)\n"
        ),
        "no_files": "Nothing to organize.",
        "preview_summary": "Total: {total} files, {cats} categories.",
        "verbose_hint": (
            "Tip: a file in the wrong category? Tick 'Diagnostic details' "
            "and re-run Preview."
        ),
        "preview_done": "Preview ready: {n} files.",
        "organize_header": "=== Organizing: {path} ===",
        "organize_done_status": "Done: {moved} moved, {errors} errors.",
        "organize_done_log": "\nDone. {moved} file(s) moved, {errors} error(s).",
        "undo_header": "=== Undoing: {date} ===",
        "undo_done": "Undo complete.",
        "undo_done_log": (
            "\nUndo complete. {moved} restored, {errors} error(s)."
        ),
        "undo_no_history": "Nothing to undo.",
        "undo_read_error": "Could not read undo log:\n{err}",
        "scanning_progress": "Scanning {i}/{total}: {name}",
        "error_label": "ERROR",
        "skipped_missing": "SKIPPED (missing): {name}",
        "reason_name": "name: '{m}'",
        "reason_camelcase_cv": "name: CamelCase '{m}'",
        "reason_ext": "ext {ext}",
        "reason_ext_with_content": "ext {ext} ({note})",
        "reason_ext_no_match": "no extension match: {ext}",
        "reason_no_match_with_note": "no extension match ({note})",
        "reason_content_strong": "{src} content strong: {kws}",
        "reason_content_weak": "{src} content weak x{n}: {kws}",
        "reason_content_no_text": "{src} no text (scanned or encrypted)",
        "reason_content_not_cv_weak": "{src} not a CV (weak x{n}: {kws})",
        "reason_content_not_cv": "{src} not a CV ({n} chars, no match)",
        "warn_undo_write_failed": "WARNING: could not write undo log: {err}",
        "fatal_error": "\nFATAL ERROR: {err}",
        "error_done": "Error.",
        "empty_done": "Empty.",
    },
    "tr": {
        "app_title": "Dosya Düzenleyici",
        "folder_label": "Klasör:",
        "browse_btn": "Gözat...",
        "preview_btn": "Önizle",
        "organize_btn": "Düzenle",
        "undo_btn": "Geri Al",
        "verbose_check": "Tanı detayları",
        "clear_log_btn": "Logu Temizle",
        "status_ready": "Hazır.",
        "menu_file": "Dosya",
        "menu_exit": "Çıkış",
        "menu_settings": "Ayarlar",
        "menu_preferences": "Tercihler...",
        "menu_help": "Yardım",
        "menu_about": "Hakkında",
        "settings_title": "Tercihler",
        "settings_language": "Dil:",
        "settings_save": "Kaydet",
        "settings_cancel": "İptal",
        "settings_restart_note": "Dil değişikliği anında geçerli olur.",
        "about_title": "Hakkında",
        "about_body": (
            "{app} v{ver}\n\nBağımsız bir dosya düzenleyici.\n"
            "Tek .exe, kurulum yok."
        ),
        "bmc_label": "Projeyi destekle",
        "pick_folder_first": "Önce bir klasör seç.",
        "folder_not_found": "Klasör bulunamadı:\n{path}",
        "confirm_organize": (
            "{path}\n\nKlasör içindeki dosyalar kategori alt klasörlerine "
            "taşınacak. Devam edilsin mi?"
        ),
        "confirm_undo": (
            "Son işlem {date} tarihinde {n} dosya taşıdı. Geri alınsın mı?"
        ),
        "preview_header": "=== Önizleme: {path} ===",
        "preview_scanning": "(PDF ve Word dosyaları CV içeriği için taranıyor...)\n",
        "no_files": "Düzenlenecek dosya yok.",
        "preview_summary": "Toplam: {total} dosya, {cats} kategori.",
        "verbose_hint": (
            "İpucu: Bir dosya yanlış kategoride mi? 'Tanı detayları'nı aç "
            "ve tekrar Önizle."
        ),
        "preview_done": "Önizleme hazır: {n} dosya.",
        "organize_header": "=== Düzenleniyor: {path} ===",
        "organize_done_status": "Bitti: {moved} taşındı, {errors} hata.",
        "organize_done_log": "\nBitti. {moved} dosya taşındı, {errors} hata.",
        "undo_header": "=== Geri alınıyor: {date} ===",
        "undo_done": "Geri alındı.",
        "undo_done_log": "\nGeri alma bitti. {moved} dosya, {errors} hata.",
        "undo_no_history": "Geri alınacak işlem yok.",
        "undo_read_error": "Geri-al kütüğü okunamadı:\n{err}",
        "scanning_progress": "İnceleniyor {i}/{total}: {name}",
        "error_label": "HATA",
        "skipped_missing": "ATLANDI (kayıp): {name}",
        "reason_name": "isim: '{m}'",
        "reason_camelcase_cv": "isim: CamelCase '{m}'",
        "reason_ext": "uzantı {ext}",
        "reason_ext_with_content": "uzantı {ext} ({note})",
        "reason_ext_no_match": "uzantı eşleşmedi: {ext}",
        "reason_no_match_with_note": "uzantı eşleşmedi ({note})",
        "reason_content_strong": "{src} içerik güçlü: {kws}",
        "reason_content_weak": "{src} içerik zayıf x{n}: {kws}",
        "reason_content_no_text": "{src} metin yok (taranmış/şifreli olabilir)",
        "reason_content_not_cv_weak": "{src} CV değil (zayıf x{n}: {kws})",
        "reason_content_not_cv": "{src} CV değil ({n} karakter, eşleşme yok)",
        "warn_undo_write_failed": "UYARI: Geri-al kütüğü yazılamadı: {err}",
        "fatal_error": "\nKRİTİK HATA: {err}",
        "error_done": "Hata.",
        "empty_done": "Boş.",
    },
}


class I18N:
    """Tiny translation lookup with a default-language fallback."""

    def __init__(self, lang: str = DEFAULT_LANG) -> None:
        self._lang = lang if lang in UI_STRINGS else DEFAULT_LANG

    @property
    def lang(self) -> str:
        return self._lang

    def set_language(self, lang: str) -> None:
        if lang in UI_STRINGS:
            self._lang = lang

    def t(self, key: str, **kwargs) -> str:
        table = UI_STRINGS.get(self._lang, UI_STRINGS[DEFAULT_LANG])
        text = table.get(key) or UI_STRINGS[DEFAULT_LANG].get(key, key)
        return text.format(**kwargs) if kwargs else text


i18n = I18N()


# ---------------------------------------------------------------------------
# Category definitions
#
# Internal keys are stable across languages. Localized display names are
# defined per-language; the on-disk folder is named in the active language.
# ---------------------------------------------------------------------------

CATEGORY_NAMES = {
    "en": {
        "cv": "CV",
        "invoices": "Invoices",
        "payroll": "Payroll",
        "bank": "Bank",
        "tax": "Tax",
        "telecom": "Telecom",
        "insurance": "Insurance",
        "contracts": "Contracts",
        "housing": "Housing",
        "tickets": "Tickets",
        "visa": "Visa",
        "official": "Official Documents",
        "exams": "Exams",
        "manuals": "Manuals",
        "returns": "Returns",
        "logs": "Logs",
        "vehicles": "Vehicles",
        "screenshots": "Screenshots",
        "installers": "Installers",
        "documents": "Documents",
        "spreadsheets": "Spreadsheets",
        "presentations": "Presentations",
        "images": "Images",
        "videos": "Videos",
        "music": "Music",
        "archives": "Archives",
        "code": "Code",
        "fonts": "Fonts",
        "disk_images": "Disk Images",
        "torrents": "Torrents",
        "other": "Other",
    },
    "tr": {
        "cv": "CV",
        "invoices": "Faturalar",
        "payroll": "Bordro",
        "bank": "Banka",
        "tax": "Vergi",
        "telecom": "Telekom",
        "insurance": "Sigorta",
        "contracts": "Sözleşme",
        "housing": "Konut",
        "tickets": "Bilet",
        "visa": "Vize",
        "official": "Resmi Belge",
        "exams": "Sınav",
        "manuals": "Kılavuz",
        "returns": "İade",
        "logs": "Loglar",
        "vehicles": "Araç",
        "screenshots": "Ekran Görüntüleri",
        "installers": "Kurulum",
        "documents": "Belgeler",
        "spreadsheets": "Tablolar",
        "presentations": "Sunumlar",
        "images": "Resimler",
        "videos": "Videolar",
        "music": "Müzik",
        "archives": "Arşivler",
        "code": "Kod",
        "fonts": "Yazı Tipleri",
        "disk_images": "Disk Kalıbı",
        "torrents": "Torrent",
        "other": "Diğer",
    },
}


def category_display(key: str, lang: str | None = None) -> str:
    """Localized folder/display name for an internal category key."""
    lang = lang or i18n.lang
    return CATEGORY_NAMES.get(lang, CATEGORY_NAMES["en"]).get(key, key)


def all_category_names_for_lang(lang: str) -> set[str]:
    return set(CATEGORY_NAMES.get(lang, CATEGORY_NAMES["en"]).values())


def all_known_category_names() -> set[str]:
    """Every localized name across every supported language.

    Used when walking a folder so we never recurse into a previously created
    category subfolder, regardless of the language it was created in.
    """
    names: set[str] = set()
    for lang in CATEGORY_NAMES:
        names |= all_category_names_for_lang(lang)
    return names


# ---------------------------------------------------------------------------
# Text normalization and CV-content detection
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    """Lowercase, strip diacritics, fold dotless ı to i.

    The dotless ı (U+0131) is a standalone letter rather than a combining
    sequence, so NFD does not decompose it. We fold it explicitly so that
    Turkish filenames like 'Kılavuz' match the keyword 'kilavuz'.
    """
    s = unicodedata.normalize("NFD", s.casefold())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("ı", "i")


def _maybe_despace(text: str) -> str:
    """Repair PDF text that was rendered character-by-character.

    Some PDFs (commonly those exported from Canva/Figma) place each glyph as
    its own text object. Most extractors then emit one space between every
    character: "W o r k  E x p e r i e n c e". We detect that pattern via
    the ratio of single-character tokens and collapse the inter-character
    spaces while preserving word breaks (double spaces).
    """
    tokens = text.split()
    if len(tokens) < 10:
        return text
    single = sum(1 for tok in tokens if len(tok) == 1) / len(tokens)
    if single < 0.4:
        return text
    placeholder = "\x00"
    out = re.sub(r"  +", placeholder, text)
    out = out.replace(" ", "")
    return out.replace(placeholder, " ")


_CV_STRONG_RAW = ("curriculum vitae", "özgeçmiş", "resume", "résumé")

_CV_WEAK_RAW = (
    # English headers commonly found in CVs
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
    # Turkish headers
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

_CV_STRONG = tuple(_normalize(k) for k in _CV_STRONG_RAW)
_CV_WEAK = tuple(_normalize(k) for k in _CV_WEAK_RAW)


def _read_pdf_text(path: Path, max_pages: int = 4) -> str:
    """Extract text from the first few pages. Returns '' on any failure."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            return ""
        parts = []
        for page in reader.pages[:max_pages]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts)
    except Exception:
        return ""


def _read_docx_text(path: Path) -> str:
    """Extract paragraph and table text from a .docx file."""
    try:
        from docx import Document
        doc = Document(str(path))
        chunks = [p.text for p in doc.paragraphs if p.text]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        chunks.append(cell.text)
        return "\n".join(chunks)
    except Exception:
        return ""


@functools.lru_cache(maxsize=1024)
def _read_pdf_text_cached(path_str: str, mtime: float, size: int) -> str:
    # mtime + size in the cache key invalidate the cache when the file changes
    return _read_pdf_text(Path(path_str))


@functools.lru_cache(maxsize=1024)
def _read_docx_text_cached(path_str: str, mtime: float, size: int) -> str:
    return _read_docx_text(Path(path_str))


def _aggressive_strip(s: str) -> str:
    return re.sub(r"[\s\x00-\x1f]+", "", s)


def _drop_one_variants(token: str):
    """Yield variants of `token` with one internal character removed.

    Used as a fuzzy fallback for PDFs whose font lacks unicode mappings for
    certain glyphs (commonly 'i') — those characters are silently dropped by
    text extractors, so 'education' becomes 'educaton' in the extracted text.
    """
    if len(token) < 6:
        return
    for i in range(1, len(token) - 1):
        yield token[:i] + token[i + 1:]


def cv_signals(text: str) -> tuple[list[str], list[str]]:
    """Return (strong_hits, weak_hits) for CV detection in `text`.

    Exact match first; fuzzy fallback runs only if the exact match wasn't
    decisive (< 1 strong and < 2 weak hits). Fuzzy matches are tagged with
    a trailing '(~)' so diagnostic output makes the distinction visible.
    """
    if not text:
        return [], []
    text = _maybe_despace(text)
    normalized = _normalize(text)

    strong = [kw for kw in _CV_STRONG if kw in normalized]
    weak = [kw for kw in _CV_WEAK if kw in normalized]
    if strong or len(weak) >= 2:
        return strong, weak

    compact = _aggressive_strip(normalized)
    if len(compact) < 50:
        return strong, weak

    for kw in _CV_STRONG:
        if kw in strong:
            continue
        for variant in _drop_one_variants(_aggressive_strip(kw)):
            if variant in compact:
                strong.append(kw + " (~)")
                break
    for kw in _CV_WEAK:
        if kw in weak:
            continue
        for variant in _drop_one_variants(_aggressive_strip(kw)):
            if variant in compact:
                weak.append(kw + " (~)")
                break
    return strong, weak


# ---------------------------------------------------------------------------
# Filename-pattern rules
#
# All match against the normalized filename (see _normalize). The CamelCase
# CV rule is the exception — it matches against the original name so it can
# rely on case transitions ('AcmeCV_', 'JohnCv_2025.pdf' etc.).
# ---------------------------------------------------------------------------

_LB = r"(?<![a-z0-9])"   # left boundary: no preceding letter or digit
_RB = r"(?![a-z0-9])"    # right boundary: no following letter or digit

_CAMELCASE_CV = re.compile(r"(?<=[a-z])(CV|Cv)(?=[_\-\s.]|$)")

NAME_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(_LB + r"(cv|resume|ozgecmis)" + _RB), "cv"),
    (re.compile(_LB + r"(fatura|invoice|receipt|fis|makbuz|bill)" + _RB),
     "invoices"),
    (re.compile(
        r"(screenshot|screen[\s_-]?shot|ekran[\s_-]?goruntusu|screencap)"
    ), "screenshots"),
    (re.compile(r"^(setup|installer|install)[\s_\-.]"), "installers"),
    (re.compile(
        r"(bordro|gehaltsabrechnung|lohnabrechnung|turnusabrechnung|"
        r"payslip|payroll)"
    ), "payroll"),
    (re.compile(
        r"(dekont|kontoauszug|"
        r"payment[\s_-]+confirmation|"
        r"transaction[\s_-]+details|"
        r"account[\s_-]+statement|"
        r"risk[\s_-]?merkez|"
        r"varlik[\s_-]?degisim)"
    ), "bank"),
    (re.compile(
        r"(steuerberater|mandanteninformation|finanzamt|steuererklarung|"
        r"vergi[\s_-]+(?:levha|beyanname|beyani|dairesi))"
    ), "tax"),
    (re.compile(
        r"(vodafone|turkcell|turk[\s_-]?telekom|numara[\s_-]?tasima)"
    ), "telecom"),
    # Insurance must come before visa: 'ipv antrag' belongs here.
    (re.compile(
        r"(sigorta|versicherung|sfr[\s_-]+ausland|ipv[\s_-]?antrag)"
    ), "insurance"),
    (re.compile(
        r"(sozlesme|mietvertrag|vertragsbestatigung|zusatzvereinbarung|"
        r"kundigung|vollmacht|ibraname|mitgliedschaft|ek[\s_-]+protokol)"
    ), "contracts"),
    (re.compile(
        r"(mietspiegel|yapi[\s_-]?raporu|zemin[\s_-]?yapi|"
        r"nebenkostenabrechnung|emlak|"
        r"(?<![a-z0-9])tapu(?![a-z0-9]))"
    ), "housing"),
    (re.compile(r"(bilet|ticket|boarding[\s_-]?pass)"), "tickets"),
    (re.compile(
        r"(visum|einladungsschreiben|antragszusammenfassung)"
    ), "visa"),
    (re.compile(
        r"(dijital[\s_-]?kimlik|nvi[\s_-]|emniyet[\s_-]|ehliyet|pasaport|"
        r"mezun[\s_-]?belgesi|oturum[\s_-]?uzat|sicil[\s_-]?kayd|"
        r"e[\s_-]?devlet)"
    ), "official"),
    (re.compile(r"(protokoll[\s_-]+theorie|ergebnisprotokoll)"), "exams"),
    (re.compile(
        r"(kilavuz|user[\s_-]?guide|handbuch|"
        r"(?<![a-z0-9])manual(?![a-z0-9]))"
    ), "manuals"),
    (re.compile(
        r"(?<![a-z0-9])(?:iade|refund)(?![a-z0-9])|return[\s_-]+label"
    ), "returns"),
    (re.compile(
        r"(eventlog|errorlog|crashlog|debuglog|"
        r"event[\s_-]+log|error[\s_-]+log|crash[\s_-]+log)"
    ), "logs"),
    (re.compile(
        r"(pdf-?expose-|piaggio|\blimousine\b|"
        r"(?:^|[\s_\-.])(?:bmw|mercedes|audi|vw|volkswagen|renault)[\s_\-])"
    ), "vehicles"),
]


EXT_RULES = {
    "documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md",
                  ".tex", ".epub", ".mobi", ".azw3", ".pages"},
    "spreadsheets": {".xls", ".xlsx", ".csv", ".ods", ".tsv", ".numbers"},
    "presentations": {".ppt", ".pptx", ".odp", ".key"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
               ".tif", ".svg", ".heic", ".ico", ".psd", ".ai", ".raw",
               ".cr2", ".nef"},
    "videos": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
               ".m4v", ".mpg", ".mpeg", ".3gp"},
    "music": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma",
              ".opus", ".aiff"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"},
    "installers": {".exe", ".msi", ".msix", ".appx", ".appxbundle"},
    "code": {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css",
             ".scss", ".java", ".kt", ".cpp", ".c", ".h", ".hpp", ".cs",
             ".go", ".rs", ".rb", ".php", ".swift", ".sh", ".ps1", ".bat",
             ".cmd", ".json", ".xml", ".yml", ".yaml", ".toml", ".ini",
             ".sql", ".lua", ".gd"},
    "fonts": {".ttf", ".otf", ".woff", ".woff2"},
    "disk_images": {".iso", ".img", ".dmg", ".vhd", ".vmdk"},
    "torrents": {".torrent"},
}


SKIP_NAMES = {UNDO_LOG_NAME, "desktop.ini", "Thumbs.db", "thumbs.db",
              "$RECYCLE.BIN"}


def classify_detailed(path: Path, inspect_content: bool = True
                      ) -> tuple[str, str]:
    """Return (category_key, reason_text) for a single file path.

    The reason is a short human-readable note about why the file landed in
    that category — used by the UI when diagnostic mode is on.
    """
    name = path.name

    m = _CAMELCASE_CV.search(name)
    if m:
        return "cv", i18n.t("reason_camelcase_cv", m=m.group())

    name_norm = _normalize(name)
    for pattern, key in NAME_RULES:
        m = pattern.search(name_norm)
        if m:
            return key, i18n.t("reason_name", m=m.group())

    ext = path.suffix.lower()

    if inspect_content and ext in (".pdf", ".docx"):
        try:
            stat = path.stat()
            if ext == ".pdf":
                text = _read_pdf_text_cached(
                    str(path), stat.st_mtime, stat.st_size)
                src = "PDF"
            else:
                text = _read_docx_text_cached(
                    str(path), stat.st_mtime, stat.st_size)
                src = "DOCX"
        except OSError:
            text, src = "", ext.upper().lstrip(".")

        strong, weak = cv_signals(text)
        if strong:
            return "cv", i18n.t(
                "reason_content_strong", src=src, kws=", ".join(strong[:3]))
        if len(weak) >= 2:
            return "cv", i18n.t(
                "reason_content_weak", src=src, n=len(weak),
                kws=", ".join(weak[:4]))

        # Not a CV — produce an explanatory note then fall through to ext.
        if not text:
            note = i18n.t("reason_content_no_text", src=src)
        elif weak:
            note = i18n.t(
                "reason_content_not_cv_weak", src=src, n=len(weak),
                kws=", ".join(weak[:3]))
        else:
            note = i18n.t("reason_content_not_cv", src=src, n=len(text))

        for key, exts in EXT_RULES.items():
            if ext in exts:
                return key, i18n.t(
                    "reason_ext_with_content", ext=ext, note=note)
        return "other", i18n.t("reason_no_match_with_note", note=note)

    for key, exts in EXT_RULES.items():
        if ext in exts:
            return key, i18n.t("reason_ext", ext=ext)
    return "other", i18n.t("reason_ext_no_match", ext=ext)


def classify(path: Path, inspect_content: bool = True) -> str:
    """Convenience wrapper that returns only the category key."""
    return classify_detailed(path, inspect_content)[0]


def plan_moves(root: Path, progress_cb=None, with_reason: bool = False
               ) -> list:
    """Walk `root` (top level only) and produce a move plan.

    Returns a list of tuples. Each tuple is (src, dst, category_key) or
    (src, dst, category_key, reason) when with_reason is True. `dst` is
    computed using the active locale.
    """
    skip_dirs = all_known_category_names()

    entries = []
    for entry in root.iterdir():
        if entry.is_dir():
            continue
        name = entry.name
        if name in SKIP_NAMES or name.startswith("."):
            continue
        # Defensive: in case a category folder ever shows up as a "file".
        if name in skip_dirs:
            continue
        entries.append(entry)

    moves = []
    total = len(entries)
    for i, entry in enumerate(entries, 1):
        if progress_cb:
            progress_cb(i, total, entry.name)
        key, reason = classify_detailed(entry)
        dst = root / category_display(key) / entry.name
        if with_reason:
            moves.append((entry, dst, key, reason))
        else:
            moves.append((entry, dst, key))
    return moves


def resolve_conflict(dst: Path) -> Path:
    """If `dst` exists, return a sibling path with a (1), (2), ... suffix."""
    if not dst.exists():
        return dst
    stem, suffix, parent = dst.stem, dst.suffix, dst.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class SettingsDialog(tk.Toplevel):
    """Modal preferences dialog. Currently exposes the UI language."""

    def __init__(self, master: tk.Misc, on_language_change) -> None:
        super().__init__(master)
        self.transient(master)
        self.resizable(False, False)
        self.title(i18n.t("settings_title"))
        self._on_language_change = on_language_change
        self._current_lang = i18n.lang

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=i18n.t("settings_language")).grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=4)

        self._lang_var = tk.StringVar(value=LANGUAGES[self._current_lang])
        combo = ttk.Combobox(
            frame, state="readonly",
            values=list(LANGUAGES.values()),
            textvariable=self._lang_var,
            width=20,
        )
        combo.grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(frame, text=i18n.t("settings_restart_note"),
                  foreground="#666").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=2, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(btn_row, text=i18n.t("settings_cancel"),
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(btn_row, text=i18n.t("settings_save"),
                   command=self._save).pack(side="right")

        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _save(self) -> None:
        chosen_label = self._lang_var.get()
        code = next(
            (c for c, label in LANGUAGES.items() if label == chosen_label),
            self._current_lang,
        )
        if code != self._current_lang:
            self._on_language_change(code)
        self.destroy()


class OrganizerApp:
    """The top-level Tk window and event handlers for the organizer."""

    def __init__(self, root: tk.Tk, settings: dict) -> None:
        self.root = root
        self.settings = settings
        i18n.set_language(settings.get("language", DEFAULT_LANG))

        self.folder_var = tk.StringVar()
        self.verbose_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar()
        self.msg_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()

        # Reactive widget text — updated when language changes.
        self._labels: dict[str, tk.StringVar] = {}

        self._build_menu()
        self._build_ui()
        self._apply_language()
        self.root.after(100, self._drain_queue)

    # ------- UI construction ------------------------------------------------

    def _label_var(self, key: str) -> tk.StringVar:
        if key not in self._labels:
            self._labels[key] = tk.StringVar(value=i18n.t(key))
        return self._labels[key]

    def _build_menu(self) -> None:
        bar = tk.Menu(self.root)
        self.root.config(menu=bar)

        self._menu_file = tk.Menu(bar, tearoff=0)
        self._menu_settings = tk.Menu(bar, tearoff=0)
        self._menu_help = tk.Menu(bar, tearoff=0)

        bar.add_cascade(menu=self._menu_file, label=i18n.t("menu_file"))
        bar.add_cascade(menu=self._menu_settings,
                        label=i18n.t("menu_settings"))
        bar.add_cascade(menu=self._menu_help, label=i18n.t("menu_help"))

        self._menu_file.add_command(
            label=i18n.t("menu_exit"), command=self.root.destroy)
        self._menu_settings.add_command(
            label=i18n.t("menu_preferences"), command=self._open_settings)
        self._menu_help.add_command(
            label=i18n.t("menu_about"), command=self._show_about)

        self._menubar = bar

    def _build_ui(self) -> None:
        self.root.title(i18n.t("app_title"))
        self.root.geometry("860x600")
        self.root.minsize(700, 480)

        pad = {"padx": 10, "pady": 6}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, textvariable=self._label_var("folder_label")).pack(
            side="left")
        ttk.Entry(top, textvariable=self.folder_var).pack(
            side="left", fill="x", expand=True, padx=(6, 6))
        self.browse_btn = ttk.Button(
            top, textvariable=self._label_var("browse_btn"),
            command=self._browse)
        self.browse_btn.pack(side="left")

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", **pad)
        self.preview_btn = ttk.Button(
            actions, textvariable=self._label_var("preview_btn"),
            command=self._preview)
        self.preview_btn.pack(side="left", padx=(0, 6))
        self.organize_btn = ttk.Button(
            actions, textvariable=self._label_var("organize_btn"),
            command=self._organize)
        self.organize_btn.pack(side="left", padx=(0, 6))
        self.undo_btn = ttk.Button(
            actions, textvariable=self._label_var("undo_btn"),
            command=self._undo)
        self.undo_btn.pack(side="left", padx=(0, 6))
        ttk.Checkbutton(
            actions, textvariable=self._label_var("verbose_check"),
            variable=self.verbose_var).pack(side="left", padx=(12, 0))
        ttk.Button(
            actions, textvariable=self._label_var("clear_log_btn"),
            command=self._clear_log).pack(side="right")

        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill="x", **pad)

        self.status_var.set(i18n.t("status_ready"))
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(
            fill="x", padx=10)

        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, wrap="none", font=("Consolas", 9))
        yscroll = ttk.Scrollbar(log_frame, orient="vertical",
                                command=self.log.yview)
        xscroll = ttk.Scrollbar(log_frame, orient="horizontal",
                                command=self.log.xview)
        self.log.configure(yscrollcommand=yscroll.set,
                           xscrollcommand=xscroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        footer = ttk.Frame(self.root)
        footer.pack(fill="x", padx=10, pady=(0, 8))
        self.bmc_link = tk.Label(
            footer, text="", fg="#1f6feb", cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        )
        self.bmc_link.pack(side="right")
        self.bmc_link.bind("<Button-1>", lambda _e: webbrowser.open(BMC_URL))

    def _apply_language(self) -> None:
        """Refresh every translatable label after a language change."""
        self.root.title(i18n.t("app_title"))
        for key, var in self._labels.items():
            var.set(i18n.t(key))
        self.status_var.set(i18n.t("status_ready"))

        # Menu cascade labels do not bind to StringVars cleanly across
        # platforms — easier to rebuild the whole menu from scratch.
        self._build_menu()

        # Footer link uses the localized phrasing + URL.
        self.bmc_link.config(text=f"{i18n.t('bmc_label')}  -  {BMC_URL}")

    # ------- Menu actions ---------------------------------------------------

    def _open_settings(self) -> None:
        SettingsDialog(self.root, on_language_change=self._change_language)

    def _change_language(self, code: str) -> None:
        i18n.set_language(code)
        self.settings["language"] = code
        save_settings(self.settings)
        self._apply_language()

    def _show_about(self) -> None:
        messagebox.showinfo(
            i18n.t("about_title"),
            i18n.t("about_body", app=APP_NAME, ver=APP_VERSION),
        )

    # ------- Helpers --------------------------------------------------------

    def _browse(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def _log_line(self, msg: str) -> None:
        self.log.insert(END, msg + "\n")
        self.log.see(END)

    def _clear_log(self) -> None:
        self.log.delete("1.0", END)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for btn in (self.preview_btn, self.organize_btn, self.undo_btn):
            btn.config(state=state)

    def _resolve_root(self) -> Path | None:
        raw = self.folder_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning(
                i18n.t("app_title"), i18n.t("pick_folder_first"))
            return None
        root = Path(raw)
        if not root.is_dir():
            messagebox.showerror(
                i18n.t("app_title"),
                i18n.t("folder_not_found", path=raw))
            return None
        return root

    # ------- Preview --------------------------------------------------------

    def _preview(self) -> None:
        root = self._resolve_root()
        if not root:
            return
        self._clear_log()
        self._log_line(i18n.t("preview_header", path=root))
        self._log_line(i18n.t("preview_scanning"))
        self._set_busy(True)
        verbose = self.verbose_var.get()
        threading.Thread(
            target=self._preview_worker, args=(root, verbose),
            daemon=True,
        ).start()

    def _preview_worker(self, root: Path, verbose: bool) -> None:
        def progress(i, total, name):
            self.msg_queue.put(("progress_max", total))
            self.msg_queue.put(("progress", i))
            self.msg_queue.put((
                "status",
                i18n.t("scanning_progress", i=i, total=total, name=name),
            ))
        try:
            moves = plan_moves(root, progress_cb=progress, with_reason=True)
            if not moves:
                self.msg_queue.put(("log", i18n.t("no_files")))
                self.msg_queue.put(("done", i18n.t("empty_done")))
                return

            grouped: dict[str, list[tuple[str, str]]] = {}
            for src, _dst, key, reason in moves:
                label = category_display(key)
                grouped.setdefault(label, []).append((src.name, reason))

            for label in sorted(grouped):
                self.msg_queue.put((
                    "log", f"[{label}]  ({len(grouped[label])})"))
                for name, reason in sorted(grouped[label]):
                    line = f"  - {name}    [{reason}]" if verbose \
                        else f"  - {name}"
                    self.msg_queue.put(("log", line))
                self.msg_queue.put(("log", ""))

            self.msg_queue.put((
                "log",
                i18n.t("preview_summary", total=len(moves),
                       cats=len(grouped)),
            ))
            if not verbose:
                self.msg_queue.put(("log", i18n.t("verbose_hint")))
            self.msg_queue.put((
                "done", i18n.t("preview_done", n=len(moves))))
        except Exception as e:
            self.msg_queue.put(("log", i18n.t("fatal_error", err=e)))
            self.msg_queue.put(("done", i18n.t("error_done")))

    # ------- Organize -------------------------------------------------------

    def _organize(self) -> None:
        root = self._resolve_root()
        if not root:
            return
        if not messagebox.askyesno(
            i18n.t("app_title"),
            i18n.t("confirm_organize", path=root),
        ):
            return
        self._set_busy(True)
        threading.Thread(
            target=self._organize_worker, args=(root,), daemon=True,
        ).start()

    def _organize_worker(self, root: Path) -> None:
        try:
            moves = plan_moves(root)
            self.msg_queue.put(("log", i18n.t("organize_header", path=root)))
            if not moves:
                self.msg_queue.put(("log", i18n.t("no_files")))
                self.msg_queue.put(("done", i18n.t("empty_done")))
                return
            self.msg_queue.put(("progress_max", len(moves)))

            undo_records = []
            errors = 0
            timestamp = datetime.now().isoformat(timespec="seconds")

            for i, (src, dst, key) in enumerate(moves, 1):
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    final = resolve_conflict(dst)
                    shutil.move(str(src), str(final))
                    undo_records.append({
                        "from": str(final), "to": str(src),
                    })
                    self.msg_queue.put((
                        "log",
                        f"[{category_display(key)}] {src.name}",
                    ))
                except Exception as e:
                    errors += 1
                    self.msg_queue.put((
                        "log",
                        f"{i18n.t('error_label')}: {src.name} -> {e}",
                    ))
                self.msg_queue.put(("progress", i))

            self._append_undo(root, timestamp, undo_records)
            self.msg_queue.put((
                "log",
                i18n.t("organize_done_log",
                       moved=len(undo_records), errors=errors),
            ))
            self.msg_queue.put((
                "done",
                i18n.t("organize_done_status",
                       moved=len(undo_records), errors=errors),
            ))
        except Exception as e:
            self.msg_queue.put(("log", i18n.t("fatal_error", err=e)))
            self.msg_queue.put(("done", i18n.t("error_done")))

    def _append_undo(self, root: Path, timestamp: str,
                     records: list[dict]) -> None:
        undo_path = root / UNDO_LOG_NAME
        history = []
        if undo_path.exists():
            try:
                history = json.loads(undo_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                history = []
        history.append({"timestamp": timestamp, "moves": records})
        try:
            undo_path.write_text(
                json.dumps(history, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            self.msg_queue.put((
                "log", i18n.t("warn_undo_write_failed", err=e)))

    # ------- Undo -----------------------------------------------------------

    def _undo(self) -> None:
        root = self._resolve_root()
        if not root:
            return
        undo_path = root / UNDO_LOG_NAME
        if not undo_path.exists():
            messagebox.showinfo(
                i18n.t("app_title"), i18n.t("undo_no_history"))
            return
        try:
            history = json.loads(undo_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            messagebox.showerror(
                i18n.t("app_title"),
                i18n.t("undo_read_error", err=e))
            return
        if not history:
            messagebox.showinfo(
                i18n.t("app_title"), i18n.t("undo_no_history"))
            return

        last = history[-1]
        if not messagebox.askyesno(
            i18n.t("app_title"),
            i18n.t("confirm_undo",
                   n=len(last["moves"]), date=last["timestamp"]),
        ):
            return

        self._set_busy(True)
        threading.Thread(
            target=self._undo_worker, args=(root, history),
            daemon=True,
        ).start()

    def _undo_worker(self, root: Path, history: list) -> None:
        try:
            last = history.pop()
            self.msg_queue.put((
                "log", i18n.t("undo_header", date=last["timestamp"])))
            moves = last["moves"]
            self.msg_queue.put(("progress_max", len(moves)))
            errors = 0
            for i, m in enumerate(reversed(moves), 1):
                src, dst = Path(m["from"]), Path(m["to"])
                try:
                    if src.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        final = resolve_conflict(dst)
                        shutil.move(str(src), str(final))
                        self.msg_queue.put(("log", f"<- {final.name}"))
                    else:
                        self.msg_queue.put((
                            "log", i18n.t("skipped_missing", name=src.name)))
                except Exception as e:
                    errors += 1
                    self.msg_queue.put((
                        "log",
                        f"{i18n.t('error_label')}: {src} -> {e}",
                    ))
                self.msg_queue.put(("progress", i))

            # Remove now-empty category folders (any language).
            for label in all_known_category_names():
                folder = root / label
                if folder.is_dir():
                    try:
                        if not any(folder.iterdir()):
                            folder.rmdir()
                    except OSError:
                        pass

            self._save_remaining_undo(root, history)
            self.msg_queue.put((
                "log",
                i18n.t("undo_done_log",
                       moved=len(moves) - errors, errors=errors),
            ))
            self.msg_queue.put(("done", i18n.t("undo_done")))
        except Exception as e:
            self.msg_queue.put(("log", i18n.t("fatal_error", err=e)))
            self.msg_queue.put(("done", i18n.t("error_done")))

    @staticmethod
    def _save_remaining_undo(root: Path, history: list) -> None:
        undo_path = root / UNDO_LOG_NAME
        if history:
            try:
                undo_path.write_text(
                    json.dumps(history, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError:
                pass
        else:
            try:
                undo_path.unlink()
            except OSError:
                pass

    # ------- Message pump ---------------------------------------------------

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log_line(payload)
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    settings = load_settings()
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except tk.TclError:
        pass
    OrganizerApp(root, settings)
    root.mainloop()


if __name__ == "__main__":
    main()

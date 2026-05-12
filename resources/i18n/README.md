# Translations

The app's interface is fully translatable. Each language lives in its own
JSON file in this directory.

## File format

Every file has the same shape:

```json
{
  "_meta": {
    "code": "xx",
    "name": "Display name shown in Settings"
  },
  "strings": {
    "app_title": "...",
    ...
  },
  "categories": {
    "cv": "...",
    "invoices": "...",
    ...
  }
}
```

- `_meta.code` — ISO 639-1 language code (`en`, `tr`, `de`, `es`, `fr`, ...).
  Used as the on-disk key and saved in user settings.
- `_meta.name` — Native display name shown in the language picker.
- `strings` — UI labels, buttons, dialogs, error messages.
- `categories` — Category folder names. **These are what appear on disk as
  folder names**, so pick natural translations users would expect.

## Adding a new language

1. Copy `en.json` to `<code>.json` (e.g. `de.json` for German).
2. Update `_meta.code` and `_meta.name`.
3. Translate every value in `strings` and `categories`.
   - Keys must stay exactly as in `en.json` — do not translate keys.
4. Restart the app. The new language appears in **Settings → Preferences**.

## Placeholder tokens

Strings can contain `{name}`-style placeholders that the app fills in at
runtime. Keep them intact and in the same position language allows. Common
ones:

| Token | Where it appears |
|---|---|
| `{path}`, `{folder}` | A filesystem path |
| `{name}` | A filename |
| `{n}`, `{total}`, `{cats}`, `{moved}`, `{errors}` | Counts |
| `{src}`, `{ext}`, `{kws}` | Origin/extension/keyword list |
| `{ver}`, `{cur}`, `{version}`, `{app}` | Version / app identifiers |
| `{size}`, `{elapsed}` | Human-readable size / seconds |
| `{date}` | Timestamp string |
| `{err}` | Error message text |
| `{m}` | Regex match for filename classification |
| `{i}` | Current index during progress |

## Fallbacks

If a key is missing in your file, the app falls back to English. So a
half-finished translation is still usable — you can submit progress and
fill in the rest later.

## Pull requests welcome

Open a PR adding your `<code>.json` and we'll review for naming and tone.
No Python knowledge required.

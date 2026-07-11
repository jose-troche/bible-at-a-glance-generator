# Bible Chart Generator

Regenerates the single-page "Bible at a Glance" PDF from a plain data file.
Edit the text, rerun the script — no need to touch any layout code.

## Files

- **`bible_data.yaml`** — all editable content: title, whole-Bible summary,
  timeline events, and every section/book with its summary. **This is the
  only file you should normally need to edit.**
- **`generate_chart.py`** — reads the YAML and draws the PDF. Fonts, text
  wrapping, and card sizes all auto-fit to whatever content is in the YAML.

## Setup (one time)

Requires Python 3.8+.

```bash
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Generate the PDF

Activate the virtual environment first if it isn't already active:

```bash
source venv/bin/activate      # on Windows: venv\Scripts\activate
python generate_chart.py
```

This reads `bible_data.yaml` and writes `bible_chart.pdf` in the same
folder — a single letter-size landscape page, matching the version already
delivered to you.

### Options

```bash
python generate_chart.py --data my_edited_data.yaml --output my_chart.pdf
python generate_chart.py --page-size a4          # a4 | letter | tabloid
python generate_chart.py --page-size 13x9        # custom size, inches
python generate_chart.py --portrait              # portrait instead of landscape
```

## Editing content

Open `bible_data.yaml` in any text editor. A few notes:

- Book summaries live under each section's `books:` list as `name:` /
  `summary:` pairs — edit the text directly.
- The whole-Bible summary is one YAML block under `summary:`.
- Timeline events are under `timeline:` — each has a `name`, `date`, and
  `era` (`old` or `new`, which controls the dot color). A single
  `{break: "..."}` entry draws the "silent years" gap marker.
- If you add or remove books from a section, you don't need to update any
  column/row math — `generate_chart.py` recalculates the grid automatically
  from the book count and the `rows:` value set per testament (default 3).
- If a line of text contains a colon followed by a space (e.g. `Title: a
  subtitle`), wrap the whole value in quotes so YAML doesn't misread it:
  `summary: "Title: a subtitle"`.

## When text gets too long

The script always keeps everything on one page and will **never silently
cut off text** — if a card's text can't fit even at the smallest allowed
font, it's reported as `OVERFLOW` in the terminal output along with which
book(s) are affected, so you know exactly what to shorten.

It also prints the font size it landed on for each testament. If that size
gets uncomfortably small (this prints as a warning below ~4.2pt), your
options are:

1. Trim some of the longer summaries.
2. Increase the page size (`--page-size tabloid` or a large custom size).
3. Split into two documents — copy `bible_data.yaml`, delete one
   testament's `sections:` from each copy, and run the script once per
   copy for two single-testament pages instead of one combined page.

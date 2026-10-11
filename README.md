# Scholen Den Haag: school register and map

This folder holds a list of every primary school location in Den Haag ('s-Gravenhage) and a map that shows them. The
list combines three files:

- the official school list from DUO (the government's education agency);
- CRM data export;
- Planned Culture data export.

Every school building gets its own permanent number, called the **UNIEK_ID** (for example `DH-0042`), that you can use
to track it.

There are two things you can do with this folder:

1. **Look at the map and the Excel file.** Nothing to install. See [Part 1](#part-1-look-at-the-map) and
   [Part 2](#part-2-read-the-excel-file).
2. **Make a new version of the list**, for example after a new CRM export. This needs a one-time setup of about 15
   minutes. See [Part 3](#part-3-make-a-new-version-of-the-list).

---

## What is in this folder

| Folder or file | What it is |
|---|---|
| `output/dashboard.html` | **The map.** Double-click to open it in your browser. |
| `output/scholen_den_haag.xlsx` | **The school list** (Excel). |
| `data/` | The input files: the DUO list, the CRM export and the Planned Culture export. **The CRM and Planned Culture exports are not in the GitHub repository**, because they contain personal data (names, e-mail addresses and phone numbers of contact persons). Put them in this folder yourself. |
| `data/external/` and `data/cache/` | Official data the program downloaded (DUO, RIO, CBS, address register). Do not edit. |
| `school_register/` | The program itself. You do not need to open this. |
| `requirements.txt` | The list of add-ons the program needs (used during setup). |
| `README.md` | This guide. |

---

## Part 1: Look at the map

1. Open the `output` folder.
2. Double-click **`dashboard.html`**. It opens in your web browser (Chrome, Edge or Firefox).
3. You need an internet connection for the background map. The school data itself is inside the file.

**What you can do on the map**

- **Click a circle** to see all the information about that school on the right (at the bottom on a phone).
- **Hover over a circle** to see the school's name and address.
- **Search** with the box on the right: type part of a name, address, code or wijk.
- **Switch the colours** with the *Kleur* buttons at the top:
  - **Datakwaliteit:** a **blue** circle means the data is certain. An **orange** circle with a dashed edge means
    something is uncertain; click it to read what.
    - Click the legend buttons to hide or show either group.
  - **Score 2025** and **Score 2026 (voorlopig):** the CBS *achterstandsscore*.
    - Grey means 0 (below the threshold, so no extra budget).
    - Light to dark blue means a higher score.
    - A hollow ring means no score, for example a building that belongs to a larger school, or a private school.
    - The 2026 scores use a new CBS method, so you cannot compare them with 2025.

**Showing an edited Excel file on the map**

The map has the list built in. To show a newer or edited Excel file, click **Open dataset (.xlsx)**, or drag the Excel
file onto the map. The file must keep the sheet name `Scholen` and the columns `LATITUDE` and `LONGITUDE`.

**Sharing the map**

You can e-mail `dashboard.html` to a colleague. It is a single file, and they open it the same way.

---

## Part 2: Read the Excel file

Open `output/scholen_den_haag.xlsx`. It has five sheets.

| Sheet | What it shows |
|---|---|
| **Scholen** | The list: one row per school building in Den Haag. Rows with something uncertain are coloured yellow. |
| **Koppeling** | Which CRM, Planned Culture and DUO records belong to each UNIEK_ID. Use this to put the UNIEK_ID into the CRM. |
| **Correcties CRM-PC** | Mistakes found in **our own** CRM and Planned Culture files, with the correct value and where it comes from. |
| **Uitgesloten** | Records that are not in the list, with the reason (test records, secondary schools, special education, …). |
| **Toelichting** | Where every column comes from, what every remark means, and the highest UNIEK_ID handed out so far. |

### The column DATA_KWALITEIT

- **Empty:** the data in this row is certain. It comes from official sources and nothing contradicts it.
- **Filled in:** something is uncertain. The text (in Dutch) says what, for example:
  - *Locatie niet bevestigd door RIO*: the official building register (RIO) does not know this address for this
    school. It may have closed or moved. Check with the school.
  - *Volgens RIO is het lesgebouw van …*: DUO and RIO name different buildings. The address is not changed
    automatically.
  - *Niet in DUO of RIO*: a foreign or weekend school that is in no Dutch register. Its data comes only from our own
    files.

The **Toelichting** sheet explains every remark.

### Several rows with the same VESTIGINGSCODE

That is correct. Some schools have more than one building, for example the Haagsche Schoolvereeniging has five. Each
building is its own row with its own UNIEK_ID, and they all share the school's official code.

### Fix mistakes at the source, not in this Excel file

The Excel file is **rebuilt from scratch** every time the list is made again (Part 3). Changes you type into it are
lost then. Instead:

- correct the CRM or Planned Culture (the **Correcties CRM-PC** sheet tells you what to change), and
- make a new version of the list.

---

## Part 3: Make a new version of the list

Do this when you have new exports, or every few months to pick up changes in the official data.

### One-time setup

You need a program called **Python** (free) and a few add-ons. You only do this once per computer.

**On Windows**

1. **Copy the whole project folder** to your computer, for example to `Documents\olphie`. Copy all of it, including
   `data` and `output`.
2. **Install Python**:
   - go to <https://www.python.org/downloads/>;
   - download **Python 3.12** (versions 3.11 and 3.13 also work; do not use 3.14 or newer);
   - run the installer;
   - on the first screen, **tick "Add python.exe to PATH"**, then click *Install Now*.
3. **Open a command window in the project folder**:
   - open the project folder in File Explorer;
   - click the address bar at the top (where the folder path is shown);
   - type `powershell` and press Enter.

   A blue or black window opens. This is where you type the commands below.
4. **Type these two commands**. Press Enter after each one and wait until it finishes. The second takes a minute or
   two and prints a lot of text; that is normal.

   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```

**On Mac or Linux**

1. Copy the whole project folder to your computer.
2. Install Python 3.12 from <https://www.python.org/downloads/>. On Linux, use your package manager.
3. Open the *Terminal* app and go to the project folder. Type `cd`, a space, then drag the folder into the window and
   press Enter.
4. Type:

   ```
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

### Every time you make a new version

1. **Put the new exports in the `data` folder**, replacing the old files. If you downloaded the project from GitHub,
   the CRM and Planned Culture exports are not there yet; add them. Use **exactly the same file names**:

   | File | What it is |
   |---|---|
   | `data/CRM_Export.xlsx` | Export from the CRM, with the same columns as before. |
   | `data/Planned_Culture.csv` | Export from Planned Culture (semicolon-separated CSV). |
   | `data/DUO_02-alle-schoolvestigingen-basisonderwijs.xlsx` | The DUO list "Alle vestigingen basisonderwijs". Optional: only replace it if you downloaded a newer one. |

2. **Close the Excel file** `output/scholen_den_haag.xlsx` if it is open. Otherwise it cannot be overwritten.
3. **Open the command window in the project folder** (see step 3 of the setup) and type:
   - on Windows:

     ```
     .venv\Scripts\python -m school_register
     ```

   - on Mac or Linux:

     ```
     .venv/bin/python -m school_register
     ```

4. After a few seconds you see a short summary: how many schools there are, how many have a remark, how many
   corrections were found, and where the files were written. **The new Excel file and map are now in the `output`
   folder.** Open the map again (or refresh the page) to see the new data.

You need an internet connection the first time, and whenever the official data is refreshed (see below).

### Refreshing the official data

The program downloads official data once and keeps a copy, so later runs are fast and give the same result. To get
fresh data, **delete** the folder or file below and run the program again. It downloads a new copy.

| Delete this | To refresh |
|---|---|
| `data/external/rio` | **RIO**, the official register of school buildings (DUO updates it daily). Do this every few months. |
| `data/external/besturenbo.csv` | The official names of school boards (DUO). |
| `data/cache/pdok.json` | Map positions and wijk names from the national address register (BAG). Only needed if addresses changed. |
| `data/external/cbs` | The CBS *achterstandsscores* for 2025 and 2026. |

**New CBS scores** (for example for 2027) need a small change in the program before they appear. Ask a technical
colleague (see the end of this guide).

---

## Important to know

- **The UNIEK_ID stays the same between versions.** The program reads the previous `output/scholen_den_haag.xlsx` and
  gives each school its old number back. A new school gets the next free number, and numbers are never reused.
  - **Never delete, rename or move `output/scholen_den_haag.xlsx`.** Without it, all schools are numbered again from
    `DH-0001`, and the numbers no longer match what you stored elsewhere.
  - Keep a copy of it somewhere safe. If you use the GitHub repository, ask a technical colleague to put the new
    `output` folder into it after every run, so everyone keeps the same IDs.
- **Personal data stays out of GitHub.** The CRM and Planned Culture exports are kept out of the repository on
  purpose (see `.gitignore`). The generated files in `output` only contain school-level data.
- **Only primary schools in the municipality of 's-Gravenhage are included.** Secondary schools, special education
  (sbo, so, vso) and test records are left out on purpose. They are listed on the *Uitgesloten* sheet.
- **The official data wins.** When DUO says one thing and the CRM another, the list uses DUO. The difference appears
  on the *Correcties CRM-PC* sheet.

---

## When something goes wrong

| What you see | What to do |
|---|---|
| `'python' is not recognized…` (Windows) | Python is not installed, or "Add python.exe to PATH" was not ticked. Run the Python installer again, choose *Modify*, and tick the PATH option. Then close and reopen the command window. |
| Typing `python` opens the Microsoft Store (Windows) | Python from python.org is not installed yet. Close the Store and install Python as described in setup step 2. |
| `No module named school_register` | The command window is not in the project folder. Open it again from the project folder (setup step 3). |
| `No such file or directory: .venv…` | The one-time setup was not done on this computer, or was done in another folder. Do the setup again. |
| `PermissionError` with `scholen_den_haag.xlsx` | The Excel file is still open. Close it in Excel and run again. |
| `FileNotFoundError` with a file in `data` | An input file is missing or has a different name. Check the names in the table above. |
| `KeyError` with a column name, e.g. `'Organisatie'` | An export has different columns than before. Export again with the usual columns, or ask a technical colleague. |
| An error about a connection or `HTTPError` | No internet, or a government website is temporarily down. Try again later. |
| The map is grey or white, but the circles are there | No internet connection: the background map comes from the internet. |
| *Open dataset* says `LATITUDE` and `LONGITUDE` are missing | The Excel file was changed too much. Use the file from the `output` folder. |

If an error message is not in this list, copy the full text from the command window and send it to a technical
colleague.

---

## For technical colleagues

- **Code:** the code is in `school_register/`, with tests in `tests/`.
- **Entry point:** `python -m school_register`.
- **Settings:** in `school_register/globals.py`. This holds the `GlobalSettings` dataclass, the output columns, the CBS
  score files (`CBS_SCORE_FILES`, where you add a new year) and the wijk-to-stadsdeel mapping (`WIJK_STADSDEEL`).
- **Data sources:**
  - DUO open data: vestigingen, bevoegde gezagen, and RIO onderwijslocaties and vestigingserkenningen;
  - CBS achterstandsscores;
  - PDOK Locatieserver (BAG).
- **RIO is only used to confirm or flag addresses, never to change them.** A RIO building of the same school within
  75 m of a BAG address counts as the same building (`rio_same_building_m`).
- **Automatic checks on GitHub:** GitHub Actions (`.github/workflows/tests.yml`) runs the checks below on every pull
  request and on every push to `main`. The tests run on Python 3.11, 3.12 and 3.13. Merge a pull request only when all
  checks are green.
- **Development setup and checks:**

  ```
  .venv/bin/python -m pip install -r requirements_dev.txt
  .venv/bin/python -m pytest
  .venv/bin/yapf --diff -r school_register tests
  .venv/bin/flake8 school_register tests
  .venv/bin/mypy school_register tests
  ```

---

## Licence

The code is released under the [MIT licence](LICENSE). The licence covers the code only. The data in `data/` and
`output/` comes from public government sources (DUO, RIO, CBS and the BAG) and from other sources.

# Brunot

A minimal, Python-based, local-first clone of the Bruno API client.

## Table of contents

- [Running from source](#running-from-source)
- [Overview](#overview)
- [Main window](#main-window)
- [Collections](#collections)
- [Configuration](#configuration)
- [Variable files and resolution](#variable-files-and-resolution)
- [Sending requests](#sending-requests)

## Running from source

### With uv (recommended)

From the project root:

```bash
uv sync
uv run brunot
```

### With pip (fallback)

```bash
pip install -e .
brunot
```

Then use **File → Open Collection Folder…** to open a folder of `.bru` files or pick a specific `.bru` to start from.

## Overview

- **Desktop API client** for calling and testing HTTP APIs (PySide6 + httpx).
- **Local-first, no cloud** – collections are ordinary files on disk.
- **Collections as code** – HTTP requests live in `.bru` text files that work well with Git.

Brunot can open a Bruno-style collection folder, browse requests in a tree, edit them, resolve variables from the environment and dotenv-style files, send HTTP requests, and save changes back to disk.

## Main window

The window is split into three conceptual areas:

1. **Collection tree (left)**  
   Folders and requests from the loaded collection. Click a request to open it in the editor. The tree mirrors the directory structure: each `.bru` file is a request, nested folders become nested nodes.

2. **Request editor (top right)**  
   - **Method** – GET, POST, PUT, PATCH, DELETE.  
   - **URL** – May contain `{{variable}}` placeholders.  
   - **Headers** – Key/value table (one spare empty row for quick entry).  
   - **Variables** – Values used when expanding `{{name}}` in the URL, headers, and body. Brunot discovers variable names from those fields; opening a request fills missing values from your [variable resolution](#variable-files-and-resolution) settings.  
   - **Body** – Raw request body.  
   - **Validate request** – If `Content-Type` suggests JSON, checks that the body parses as JSON; otherwise validation is skipped.  
   - **Send** – Runs the request (see [Sending requests](#sending-requests)).  
   - While a request is in flight, **Cancel** stops waiting for the response (the underlying HTTP call may still complete).  
   - **Reload variables** – Refreshes values for variables referenced in this request from the environment and active variable files, according to **Settings → Variable resolution**.  
   - **Save to variable file…** – Writes the current variable table into a chosen *active* variable file (see [Variable files](#variable-files-and-resolution)).

3. **Response viewer (bottom right)**  
   Shows status line (code, reason, timing), response headers, and a **Raw** tab with the body. JSON responses are pretty-printed when the `Content-Type` indicates JSON.

### Dialogs and menus

| Menu / action | Purpose |
|---------------|---------|
| **File → Open Collection Folder…** | First dialog: pick a `.bru` file to open its parent folder and select that request; or cancel and choose a folder to load every `.bru` under it (skips hidden dirs, `.git`, `node_modules`, etc.). |
| **File → Reload Collection** | Re-reads the collection from disk. |
| **File → Save Collection As…** | Exports the in-memory collection to a folder: writes each request to a `.bru` file (the primary file you pick, plus sibling files for other requests). |
| **File → Settings…** | Default **request timeout** (seconds) and **variable resolution** order: prefer environment variables or prefer variable files when both define the same name. |
| **File → Variable files…** | Manage [variable files](#variable-files-and-resolution): paths, enable/disable, order (higher in the list wins when the same key appears in multiple active files), and inline editing of file contents. |
| **Request → New Request…** | Adds a draft request (optionally after creating an in-memory collection if none is open). |
| **Request → Save Current Request** | Persists the active request to its `.bru` path (requires a collection rooted on disk, or save the collection first). |
| **View → Request Log** | Append-only log of sent requests, responses, errors, and cancellations (JSON payloads for inspection). |

## Collections

- A **collection** is a directory tree of `.bru` files. Subfolders appear as folders in the tree.
- **Open** via **File → Open Collection Folder…** as described above.
- **New requests**: **Request → New Request…**. If no collection exists yet, Brunot creates an in-memory collection; use **File → Save Collection As…** to write `.bru` files to disk.
- **Save one request**: **Request → Save Current Request** (needs a known save path; for an in-memory-only collection, use **Save Collection As…** first).
- **Reload** after external edits: **File → Reload Collection**.

## Configuration

Brunot merges several sources. **INI-style** `.brunot_config` files are read in this order (later overrides earlier for the same keys):

1. `.brunot_config` in the Brunot project root (useful when developing Brunot itself)
2. `~/.brunot_config`
3. `~/.config/brunot/.brunot_config`

Sections used include **`[core]`** (e.g. `timeout`, `variable_preference`), **`[variable_files]`** / **`[variable_files_enabled]`**, and **`[window]`** (window geometry hex).

Additionally, **`settings.json`** in the OS app config directory (via [platformdirs](https://pypi.org/project/platformdirs/), e.g. `~/.config/brunot/settings.json` on Linux) stores recent collections, window geometry, and request timeout. When you change settings in the UI, Brunot updates both the JSON store and the resolved `.brunot_config` write target (see `brunot/brunot_config.py` for the exact write path).

You can edit `.brunot_config` by hand for defaults; the GUI **Settings** and **Variable files** dialogs persist compatible values.

## Variable files and resolution

- **Variable files** are dotenv-style text files: `KEY=value` per line, `#` comments and blank lines ignored. Paths are configured per “file id” in **File → Variable files…**.
- Only **active** files participate in resolution. **Order matters**: for enabled files, entries are merged in list order; the **first** file in the list wins if the same variable is defined in more than one active file (use **Move up** / **Move down** in the dialog).
- **`{{name}}` syntax** in the URL, header values, and body is replaced at send time using the **Variables** table for that request.
- **Settings → Variable resolution** controls conflicts between **process environment** and **variable files**: either prefer environment variables or prefer file values first; the other source is used as fallback.
- **Reload variables** on the request editor reapplies that policy to every `{{name}}` used in the request. **Save to variable file…** merges the current table into one chosen active file on disk (sorted keys when writing).

## Sending requests

1. Select a request in the tree (or create one and fill it in).
2. Ensure every `{{variable}}` referenced in the URL, headers, or body has a non-empty value in the **Variables** table (or set them via env/files and reload). Brunot blocks **Send** if any required variable is missing.
3. Click **Send**. The app expands variables, then issues the HTTP call with the configured timeout, follows redirects, and shows the result in the **Response** area.
4. Optional: open **View → Request Log** to see a structured history of requests and responses.

Network calls use **httpx** with `trust_env=False` so inherited `HTTP_PROXY` / `NO_PROXY` environment variables do not affect the client by default (helps in some devcontainer setups).

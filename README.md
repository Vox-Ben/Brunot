# Brunot

A minimal, Python-based, local-first clone of the Bruno API client.

## Overview

- **Desktop API client** for calling and testing HTTP APIs.
- **Local-first, no cloud** – collections are just files on disk.
- **Collections as code** – HTTP requests are stored as `.bru` text files that work naturally with Git.

Brunot can open an existing Bruno collection folder, display requests, let you edit them, send HTTP requests, and save changes back to the same `.bru` files.

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

Then use **File → Open Collection Folder** to point Brunot at a folder containing `.bru` files.


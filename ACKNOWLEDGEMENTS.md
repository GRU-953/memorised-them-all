# Acknowledgements

**Memorised them All** is original, clean-room software, but it would not be
possible without the following free and open-source projects and the people
behind them. Enormous thanks to all of them.

## Core dependencies

| Project | Used for | License |
| --- | --- | --- |
| [Microsoft **MarkItDown**](https://github.com/microsoft/markitdown) | converting PDF/Office/HTML/EPub/… to Markdown (kept up to date from upstream) | MIT |
| [**Tesseract OCR**](https://github.com/tesseract-ocr/tesseract) | optical character recognition for images and scanned/broken-font PDFs (optional) | Apache-2.0 |
| [**NetworkX**](https://github.com/networkx/networkx) | graph construction and community detection | BSD-3-Clause |
| [**leidenalg**](https://github.com/vtraag/leidenalg) + [**python-igraph**](https://github.com/igraph/python-igraph) | Leiden community detection | GPL-3.0 / GPL-2.0+ (optional, used as an external tool) |
| [**RapidFuzz**](https://github.com/rapidfuzz/RapidFuzz) | fuzzy entity matching | MIT |
| [**pdfplumber**](https://github.com/jsvine/pdfplumber), [**pypdfium2**](https://github.com/pypdfium2-team/pypdfium2), [**Pillow**](https://github.com/python-pillow/Pillow), [**striprtf**](https://github.com/joshy/striprtf) | document/image handling | MIT / Apache-2.0 / HPND / BSD |
| [**Mukti**](https://github.com/anindash15-arch/Mukti) | legacy Bengali (Bijoy/SutonnyMJ ANSI) → Unicode mapping (faithfully ported to pure Python) | MIT |
| [**LibreOffice**](https://www.libreoffice.org/) | optional headless conversion of legacy binary `.doc`/`.ppt`/`.xls` | MPL-2.0 |
| [**Model Context Protocol** Python SDK](https://github.com/modelcontextprotocol/python-sdk) | the MCP server | MIT |

> Version 2 is **deterministic and model-free** — it uses **no AI models**. Earlier
> versions optionally ran local models (via Ollama) and audio transcription (Whisper),
> and rendered an interactive mind map (Cytoscape.js); all were removed in v2.

## Inspiration

- [**graphify**](https://github.com/safishamsi/graphify) by Safi Shamsi — for the
  "turn a folder into a queryable knowledge graph" vision.
- The author's own [**markitdown-mcp**](https://github.com/GRU-953/markitdown-mcp)
  and [**mnemo-mcp**](https://github.com/GRU-953/mnemo-mcp) — earlier explorations
  of token-free, local, graph-based memory. This project is a clean-room
  reimplementation, not a fork.

All trademarks and project names belong to their respective owners. If you are a
maintainer of a project listed here and would like the attribution adjusted,
please open an issue.

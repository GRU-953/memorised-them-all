# Acknowledgements

**Memorised them All** is original, clean-room software, but it would not be
possible without the following free and open-source projects and the people
behind them. Enormous thanks to all of them.

## Core dependencies

| Project | Used for | License |
| --- | --- | --- |
| [Microsoft **MarkItDown**](https://github.com/microsoft/markitdown) | converting PDF/Office/HTML/EPub/… to Markdown (kept up to date from upstream) | MIT |
| [**Ollama**](https://github.com/ollama/ollama) | running local LLMs, embeddings and vision models | MIT |
| [**Tesseract OCR**](https://github.com/tesseract-ocr/tesseract) | optical character recognition for images and scanned PDFs | Apache-2.0 |
| [**OpenAI Whisper**](https://github.com/openai/whisper) · [**faster-whisper**](https://github.com/SYSTRAN/faster-whisper) | on-device speech-to-text | MIT |
| [**Apple MLX** examples](https://github.com/ml-explore/mlx-examples) (`mlx-whisper`) | GPU-accelerated Whisper on Apple silicon | MIT |
| [**NetworkX**](https://github.com/networkx/networkx) | graph construction and community detection | BSD-3-Clause |
| [**leidenalg**](https://github.com/vtraag/leidenalg) + [**python-igraph**](https://github.com/igraph/python-igraph) | Leiden community detection | GPL-3.0 / GPL-2.0+ (optional, used as an external tool) |
| [**RapidFuzz**](https://github.com/rapidfuzz/RapidFuzz) | fuzzy entity matching | MIT |
| [**Cytoscape.js**](https://github.com/cytoscape/cytoscape.js) | the interactive offline mind map | MIT |
| [**pdfplumber**](https://github.com/jsvine/pdfplumber), [**pypdfium2**](https://github.com/pypdfium2-team/pypdfium2), [**Pillow**](https://github.com/python-pillow/Pillow), [**striprtf**](https://github.com/joshy/striprtf) | document/image handling | MIT / Apache-2.0 / HPND / BSD |
| [**Model Context Protocol** Python SDK](https://github.com/modelcontextprotocol/python-sdk) | the MCP server | MIT |

## Models (default)

- [`qwen2.5`](https://github.com/QwenLM/Qwen2.5) — knowledge extraction & summaries (Apache-2.0)
- [`nomic-embed-text`](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) — embeddings (Apache-2.0)
- [`moondream`](https://github.com/vikhyat/moondream) — image captioning (Apache-2.0)

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

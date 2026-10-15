Simple native desktop GUI for human gene literature searches.

- Enter a gene symbol/alias and an optional research topic.
- Browse article titles, abstracts, matching gene excerpts, years, journals and citations.
- Open PubMed/Europe PMC links and export CSV or HTML reports.
- No Python installation or API key required for the packaged apps; internet required for searches.

Downloads:

- **Windows x64:** extract the complete ZIP, then open `OpenGeneLiterature.exe` inside its folder. Keep `_internal` alongside the executable.
- **macOS Apple Silicon (M1/M2/M3/M4 or later):** use `macos-arm64.zip`.
- **macOS Intel:** use `macos-x64.zip`.
- On macOS, extract the ZIP and open `OpenGeneLiterature.app`.

This release is not notarized with an Apple Developer ID or signed with a Windows publisher certificate. macOS/Windows may request manual approval or block it according to device policy. Use the documented OS approval process only if you trust the download; Python source execution is also available. No security setting changes are required by the application itself.

Gene identities use HGNC (human only); searched papers may include different experimental species. Abstract excerpts are verbatim and are not AI summaries or evidence of causal regulation. This version does not implement upstream regulator or pathway analysis.

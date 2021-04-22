# PDF Parser
## Overview
Extracts text content from multi-format PDFs.

Algorithm
1. Check drm, scanned using dpi, language > 40% english. Extractable pages are drm = True, scanned = False, language_check_en = True.
2. Strip PDF page of all the lines and figures preserving only the copyable text.
3. Extract each character information (bbox,text, size, style, color, font, page_num). 

## Tools
PyMuPDF

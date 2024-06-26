# PDF Parser
**** **Updated: 9th August, 2022** ****
## Overview
PDF Parser extracts textual content from multi-format PDFs using open-source tools.

## Usage Guide
1. Install necessary packages i.e, pip install -r requirements.txt
2. Run main file i.e, python -m main
3. Send in the PDF i.e., POST Form Data

## Algorithm
- Check drm, scanned using dpi, language > 40% english. Most accurate extractions are when drm = False, scanned = False, language_check_en = True.
- **Paragraph boundary detection:** Strip PDF page of all the lines, images, objects etc. preserving only the copyable text. Extract character level information (bbox, text, size, style, color, font, page no) and write to an image. Apply image processing techniques (grayscaling, inversion, closing, thresholding, contouring) to merge character level information into a single paragraph block, thus retrieving the bbox properties of the paragraph using OpenCV. Merge overlapping bbox to retrieve unique bbox of all the paragraphs
<img src="https://user-images.githubusercontent.com/57243765/115731237-8d4f6500-a3b9-11eb-9a79-546594d9052f.png" width="200" height=auto alt="centered image"/>

- **Text content detection:** Extract span level information (bbox, text, size, style, color, font, page no) on the page using PyMuPDF. Use rectangle coordinates from paragraph boundary detection, to assign span texts to be within respective paragraphs. Join span texts accordingly to form a paragraph. Assign title and text labels based on text attributes (font, size, style).
- **Clean extracted content:** Remove border elements by restricting content to 90% width and height on all 4 corners of a PDF page. Add page breaks in cases where the PDF page contains multiple format types (e.g. single-column and multi-column on a single page), normalize block widths and merge normalized bboxs for reading sequence sorting. Merge consecutive text paragraphs within and across pages, to a single text block.
<img src="https://user-images.githubusercontent.com/57243765/115804662-0a102c80-a416-11eb-8318-ff52d86e264f.png" width = 1000 height = auto />

- **Parent child relationship:** Generate parent-child relationships between title and texts with depth levels to associate respective text to its titles.

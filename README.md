# PDF Parser
**** **Updated: 22nd April, 2021** ****
## Overview
Extracts textual content from multi-format PDFs.

## Algorithm
- Check drm, scanned using dpi, language > 40% english. Most accurate extractions are when drm = False, scanned = False, language_check_en = True.
- **Paragraph Boundary Detection:** Strip PDF page of all the lines, images, objects etc. preserving only the copyable text. Extract character level information (bbox, text, size, style, color, font, page no) and write to an image. Apply image processing techniques (grayscaling, inversion, closing, thresholding, contouring) to merge character level information into a single paragraph block, thus retrieving the bbox properties of the paragraph using OpenCV. Merge overlapping bbox to retrieve unique bbox of all the paragraphs.
- **Text Content Detection:** Extract span level information (bbox, text, size, style, color, font, page no) on the page using PyMuPDF. Use rectangle coordinates from paragraph boundary detection, to assign span texts to be within respective paragraphs. Join span texts accordingly to form a paragraph. Assign title and text labels based on text attributes (font, size, style).
- **Clean Extracted Content:** Remove border elements by restricting content to 90% width and height on all 4 corners of a PDF page. Add page breaks in cases where the PDF page contains multiple format types (e.g. single-column and multi-column on a single page), for sorting.

## Main Tools
PyMuPDF, OpenCV

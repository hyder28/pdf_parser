# PDF Parser
**** **Updated: 22nd April, 2021** ****
## Overview
Extracts textual content from multi-format PDFs.

## Algorithm
- Check drm, scanned using dpi, language > 40% english. Most accurate extractions are when drm = False, scanned = False, language_check_en = True.
- **Paragraph Detection:** Strip PDF page of all the lines, images, objects etc. preserving only the copyable text. Extract character level information (bbox, text, size, style, color, font, page no) and write to an image. Apply image processing techniques (grayscaling, inversion, closing, thresholding, contouring) to merge character level information into a single paragraph block, thus retrieving the bbox properties of the paragraph using OpenCV. Merge overlapping bbox to retrieve unique bbox of all the paragraphs.
- **Text Content Detection:** Extract span level information (bbox, text, size, style, color, font, page no) on the page using PyMuPDF. Use rectangle coordinates from paragraph detection, to assign the respective span texts within each paragraph. Assign title and text properties based on font/size/style.

## Main Tools
PyMuPDF, OpenCV

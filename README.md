# PDF Parser
## Overview
Extracts textual content from multi-format PDFs.

Algorithm
1. Check drm, scanned using dpi, language > 40% english. Most accurate extractions are when drm = False, scanned = False, language_check_en = True.
2. Strip PDF page of all the lines, images, objects etc. preserving only the copyable text. Extract character level information (bbox, text, size, style, color, font, page no) and write to an image. Apply image processing OpenCV techniques (grayscaling, inversion, closing, thresholding, contouring) to merge character level information into a single paragraph block, thus retrieving the bbox properties of the paragraph. Merge overlapping bbox.
3. Extract span level information (bbox, text, size, style, color, font, page no) on the page using PyMuPDF.
4.  




## Main Tools
PyMuPDF, OpenCV

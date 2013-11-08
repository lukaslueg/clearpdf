#!/usr/bin/env python
"""A tool to filter unwanted content (read: ads) from certain PDFs."""


import io
import re

import pyPdf
import PIL.Image


ADPAT = re.compile(r'SPONSORED (SECTION)|(CONTENT)|(REPORT)')


def scan_page(page):
    """Scan a single page and figure out the area covered by links."""
    if ADPAT.search(page.extractText()):
        return 1.0
    x1, y1, x2, y2 = page.trimBox
    pagevol = float((x2 - x1) * (y2 - y1))
    if not '/Annots' in page:
        return
    linkvol = 0.0
    for annot in page['/Annots']:
        annot = annot.getObject()
        if annot['/Subtype'] != '/Link' or '/URI' not in annot['/A']:
            continue
        x1, y1, x2, y2 = annot['/Rect']
        linkvol += float((x2 - x1) * (y2 - y1))
    return linkvol / pagevol


def filter_images(page):
    """Filter a single page and re-encode JPGs to smaller size.

    May break PDFs because the /Image-object's properties are not updated...

    """
    r = page['/Resources']
    if '/XObject' not in r:
        return
    for v in r['/XObject'].values():
        vobj = v.getObject()
        if vobj['/Subtype'] != '/Image' or '/Filter' not in vobj or \
           vobj['/Filter'] != '/DCTDecode':
            continue
        img = PIL.Image.open(io.BytesIO(vobj._data))
        newimg = io.BytesIO()
        img.save(newimg, format='JPEG', quality=50, optimize=True)
        vobj._data = newimg.getvalue()


def scan_file(fileobj):
    """Scan and filter a whole pdf-fileobj, yielding interesting pages."""
    pdf = pyPdf.PdfFileReader(fileobj)
    for i in range(pdf.getNumPages()):
        page = pdf.getPage(i)
        filter_images(page)
        yield page, scan_page(page)


def process_file(infile_name, outfile_name, threshold=0.6):
    """Process a whole PDF, writing only interesting pages to a new file."""
    with open(infile_name, 'rb') as inf:
        new_pdf = pyPdf.PdfFileWriter()
        for page, r in scan_file(inf):
            if r < threshold:
                new_pdf.addPage(page)
        with open(outfile_name, 'wb') as outf:
            new_pdf.write(outf)

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print 'Usage: %s <infile> [outfile]' % (sys.argv[0],)
        sys.exit(1)
    infile = sys.argv[1]
    outfile = sys.argv[2] if len(sys.argv) > 2 else infile + '_filtered.pdf'
    process_file(infile, outfile)

#!/usr/bin/env python
"""A tool to filter unwanted content (read: ads) from certain PDFs."""

import io
import re

import pyPdf
import PIL.Image


class FileCompressor(object):
    ADPAT = re.compile(r'SPONSORED (SECTION)|(CONTENT)|(REPORT)')

    def __init__(self, scan_full_text=True, link_threshold=0.6,
                 recompress_flate=True, recompress_jpg=True, jpg_quality=40,
                 max_w=640, max_h=480):
        self.scan_full_text = scan_full_text
        self.link_threshold = link_threshold
        self.recompress_flate = recompress_flate
        self.recompress_jpg = recompress_jpg
        self.jpg_quality = jpg_quality
        self.max_w = max_w
        self.max_h = max_h

    def _scale_image(self, img):
        """Scale an image to fit into given dimensions."""
        w, h = img.size
        if w > self.max_w:
            h /= w / self.max_w
            w = self.max_w
        if h > self.max_h:
            w /= h / self.max_h
            h = self.max_h
        if (w, h) != img.size:
            return img.resize((w, h))
        else:
            return img

    def _filter_images(self, page):
        """Filter a single page and re-encode JPGs to smaller size."""
        r = page['/Resources']
        if '/XObject' not in r:
            return
        for k, v in r['/XObject'].items():
            vobj = v.getObject()
            if vobj['/Subtype'] != '/Image' or '/Filter' not in vobj:
                continue
            if vobj['/Filter'] == '/FlateDecode':
                buf = vobj.getData()
                size = tuple(map(int, (vobj['/Width'], vobj['/Height'])))
                if len(buf) >= 1024 and vobj['/BitsPerComponent'] == 8 and \
                        len(buf) // (size[0] * size[1]) == 3:
                    img = PIL.Image.frombytes('RGB', size, buf,
                                              decoder_name='raw')
                    img = self._scale_image(img)
                    width = pyPdf.generic.NumberObject(img.size[0])
                    height = pyPdf.generic.NumberObject(img.size[1])
                    filter = pyPdf.generic.NameObject('/DCTDecode')
                    vobj[pyPdf.generic.NameObject('/Width')] = width
                    vobj[pyPdf.generic.NameObject('/Height')] = height
                    vobj[pyPdf.generic.NameObject('/Filter')] = filter
                    newimg = io.BytesIO()
                    img.save(newimg, format='JPEG', quality=self.jpg_quality,
                             optimize=True)
                    vobj._data = newimg.getvalue()
            elif vobj['/Filter'] == '/DCTDecode':
                img = PIL.Image.open(io.BytesIO(vobj._data))
                img = self._scale_image(img)
                width = pyPdf.generic.NumberObject(img.size[0])
                height = pyPdf.generic.NumberObject(img.size[1])
                vobj[pyPdf.generic.NameObject('/Width')] = width
                vobj[pyPdf.generic.NameObject('/Height')] = height
                newimg = io.BytesIO()
                img.save(newimg, format='JPEG', quality=self.jpg_quality,
                         optimize=True)
                vobj._data = newimg.getvalue()

    def _scan_page(self, page):
        """Return True if most the the given page is covered by links."""
        if self.scan_full_text and self.ADPAT.search(page.extractText()):
            return True
        x1, y1, x2, y2 = page.trimBox
        pagearea = float((x2 - x1) * (y2 - y1))
        if not '/Annots' in page:
            return
        linkarea = 0.0
        for annot in page['/Annots']:
            annot = annot.getObject()
            if annot['/Subtype'] != '/Link' or '/URI' not in annot['/A']:
                continue
            x1, y1, x2, y2 = annot['/Rect']
            linkarea += float((x2 - x1) * (y2 - y1))
        return (linkarea / pagearea) > self.link_threshold

    def process_file(self, infile_name, outfile_name):
        """Process a PDF-file, writing only interesting pages to a new file."""
        with open(infile_name, 'rb') as in_f:
            in_pdf = pyPdf.PdfFileReader(in_f)
            out_pdf = pyPdf.PdfFileWriter()
            for page_no in range(in_pdf.getNumPages()):
                page = in_pdf.getPage(page_no)
                if not self._scan_page(page):
                    self._filter_images(page)
                    out_pdf.addPage(page)
            with open(outfile_name, 'wb') as outf:
                out_pdf.write(outf)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print 'Usage: %s <infile> [outfile]' % (sys.argv[0],)
        sys.exit(1)
    infile = sys.argv[1]
    outfile = sys.argv[2] if len(sys.argv) > 2 else infile + '_filtered.pdf'
    FileCompressor().process_file(infile, outfile)

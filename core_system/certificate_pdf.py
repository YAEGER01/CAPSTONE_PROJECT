import os
import re
import subprocess
import tempfile
from pathlib import Path
from django.conf import settings
from django.template.loader import render_to_string

EDGE_PATH = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'


def generate_certificate_pdf(cert_data):
    template_data = {
        'recipient_name': cert_data.get('recipient_name', ''),
        'event_title': cert_data.get('event_title', ''),
        'event_date': cert_data.get('event_date', ''),
        'event_venue': cert_data.get('event_venue', ''),
        'day': cert_data.get('day', ''),
        'month_year': cert_data.get('month_year', ''),
        'place': cert_data.get('place', ''),
        'president_name': cert_data.get('president_name', ''),
        'president_position': cert_data.get('president_position', 'ISU-CAUFA President'),
        'secretary_name': cert_data.get('secretary_name', ''),
        'secretary_position': cert_data.get('secretary_position', 'ISU CAUFA Secretary'),
        'faculty_regent_name': cert_data.get('faculty_regent_name', ''),
        'faculty_regent_position': cert_data.get('faculty_regent_position', 'Faculty Regent'),
        'certificate_number': cert_data.get('certificate_number', ''),
        'president_signature_url': cert_data.get('president_signature_url'),
        'secretary_signature_url': cert_data.get('secretary_signature_url'),
        'faculty_regent_signature_url': cert_data.get('faculty_regent_signature_url'),
    }

    base_dir = Path(settings.BASE_DIR).resolve()
    file_base = 'file:///' + str(base_dir).replace('\\', '/')

    for key in ('president_signature_url', 'secretary_signature_url', 'faculty_regent_signature_url'):
        val = template_data.get(key)
        if val:
            if val.startswith('/'):
                template_data[key] = file_base + val
            elif os.path.isabs(val):
                template_data[key] = 'file:///' + val.replace('\\', '/')

    html = render_to_string('website/Secretary/certificate.html', template_data)
    html = html.replace('src="/static/', 'src="' + file_base + '/static/')
    html = html.replace('href="/static/', 'href="' + file_base + '/static/')

    # Force the PDF path to use the same A4 print layout as the live page.
    print_css = '''
<style>
  .toolbar, .toolbar-hint {
    display: none !important;
  }
  html, body {
    margin: 0 !important;
    padding: 0 !important;
    width: 297mm !important;
    height: 210mm !important;
    overflow: hidden !important;
    background: #fff !important;
  }
  .stage {
    width: calc(297mm - 10mm) !important;
    height: calc(210mm - 10mm) !important;
    margin: 5mm !important;
    max-width: none !important;
    aspect-ratio: auto !important;
    box-shadow: none !important;
    border-radius: 0 !important;
  }
  @page {
    size: 297mm 210mm landscape;
    margin: 0;
  }
</style>
'''
    html = html.replace('</head>', print_css + '\n</head>')

    def input_to_span(m):
        tag = m.group(0)
        v = re.search(r'value="([^"]*)"', tag)
        p = re.search(r'placeholder="([^"]*)"', tag)
        c = re.search(r'class="([^"]*)"', tag)
        text = v.group(1) if v else (p.group(1) if p else '')
        cls = ' class="' + c.group(1) + '"' if c else ''
        return '<span' + cls + '>' + text + '</span>'

    html = re.sub(r'<input[^>]*?>', input_to_span, html)

    html = re.sub(
        r'<div class="campus-input"[^>]*>(.*?)</div>',
        lambda m: '<div class="campus-input-static">' + re.sub(r'<[^>]+>', '', m.group(1)).strip() + '</div>',
        html,
        flags=re.DOTALL
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        html_path = Path(tmp_dir) / 'certificate.html'
        pdf_path = Path(tmp_dir) / 'certificate.pdf'

        html_path.write_text(html, encoding='utf-8')

        command = [
            EDGE_PATH,
            '--headless',
            '--disable-gpu',
            '--run-all-compositor-stages-before-draw',
            '--virtual-time-budget=10000',
            '--print-to-pdf-no-header',
            f'--print-to-pdf={pdf_path}',
            str(html_path)
        ]

        subprocess.run(command, check=True, capture_output=True)

        pdf_bytes = pdf_path.read_bytes()

    return pdf_bytes


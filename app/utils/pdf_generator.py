from django.template.loader import render_to_string
import os

# weasyprint is disabled due to missing system dependencies on this environment
# from weasyprint import HTML

def generate_pdf_from_html(html_string):
    """
    Generates dummy PDF bytes from an HTML string.
    """
    try:
        # pdf_bytes = HTML(string=html_string).write_pdf()
        return b"%PDF-1.4 mock data for " + html_string[:100].encode('utf-8')
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return None

def generate_pdf_from_template(template_name, context):
    """
    Renders a Django template and generates dummy PDF bytes.
    """
    html_string = render_to_string(template_name, context)
    return generate_pdf_from_html(html_string)

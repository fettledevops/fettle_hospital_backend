from django.template.loader import render_to_string
from weasyprint import HTML

def generate_pdf_from_html(html_string):
    """
    Generates real PDF bytes from an HTML string using WeasyPrint.
    """
    try:
        pdf_bytes = HTML(string=html_string).write_pdf()
        return pdf_bytes
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return None

def generate_pdf_from_template(template_name, context):
    """
    Renders a Django template and generates PDF bytes.
    """
    html_string = render_to_string(template_name, context)
    return generate_pdf_from_html(html_string)

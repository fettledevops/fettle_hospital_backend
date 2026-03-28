from django.template.loader import render_to_string

try:
    from weasyprint import HTML

    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False
    import logging

    logger = logging.getLogger(__name__)
    logger.warning(
        "WeasyPrint dependencies missing. PDF generation will fall back to mock."
    )


def generate_pdf_from_html(html_string):
    """
    Generates PDF bytes from an HTML string.
    Uses WeasyPrint if available, otherwise returns a mock byte string.
    """
    try:
        if WEASYPRINT_AVAILABLE:
            pdf_bytes = HTML(string=html_string).write_pdf()
            return pdf_bytes
        else:
            return b"%PDF-1.4 mock data - WeasyPrint not available"
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return None


def generate_pdf_from_template(template_name, context):
    """
    Renders a Django template and generates PDF bytes.
    """
    html_string = render_to_string(template_name, context)
    return generate_pdf_from_html(html_string)

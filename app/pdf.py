from docx import Document

def replace_placeholders_in_docx_preserving_styles(docx_path, output_path, replacements_dict):
    doc = Document(docx_path)

    for paragraph in doc.paragraphs:
        runs = paragraph.runs
        i = 0
        while i < len(runs):
            combined = ""
            indices = []

            j = i
            while j < len(runs):
                combined += runs[j].text
                indices.append(j)

                # Check if any placeholder is found in combined text
                match = None
                for placeholder in replacements_dict:
                    if placeholder in combined:
                        match = placeholder
                        break

                if match:
                    # Replace placeholder in combined text
                    replaced = combined.replace(match, str(replacements_dict[match]))

                    # Save formatting of first run
                    base_run = runs[indices[0]]
                    bold = base_run.bold
                    italic = base_run.italic
                    underline = base_run.underline
                    font = base_run.font.name
                    size = base_run.font.size

                    # Clear all involved runs
                    for idx in indices:
                        runs[idx].text = ""

                    # Set replaced text with preserved style in the first run
                    r = runs[indices[0]]
                    r.text = replaced
                    r.bold = bold
                    r.italic = italic
                    r.underline = underline
                    r.font.name = font
                    r.font.size = size

                    # Skip to end of matched run group
                    i = indices[-1]
                    break

                j += 1
            i += 1

    doc.save(output_path)

# 🔁 Example replacement dictionary
docx_replacements = {
    "{{reporting_period}}": "July 2025 ",
    "{{hospital_name}}": "medicity",
    "{{call_patients}}": "90",
    "{{call_answer_rate}}": "123",
    "{{community_added}}": "100",
    "{{community_conversion_rate}}": "25",
    "{{poll_number}}": "10",
    "{{escalation_number}}": "23",
    "{{revisit_conversion_rate}}": "50",
    "{{revisit_number}}": "100"
}

# 🔁 Run the replacement
replace_placeholders_in_docx_preserving_styles(
   r"Amor-Hospitals-May-2025-PTS-Report.docx",
    "out.docx",
    docx_replacements
)

import fitz  # PyMuPDF

# Load the PDF
doc = fitz.open(r"C:\Users\Prajval Bhardwaj\Downloads\Amor Hospitals June 2025 PTS Report.pdf")

# Define text replacements
replacements = {
    "946": "1021",
    "80.09%": "82.34%",
    "287": "312",
    "8.39%": "9.12%",
    "27.94%": "30.10%",
    "183": "205",
    "20 actionable feedback points": "24 actionable feedback points",
    "June 1 – June 30, 2025": "July 1 – July 31, 2025",
    "June 2025": "July 2025",
    "Ms.Padmaja who visited the psychiatry department of the hospital on 19/06/2025":
        "Mr. Arjun who visited the orthopedic department of the hospital on 15/07/2025"
}

# Loop through each page
for page in doc:
    # Get text as structured dictionary
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span["text"]
                for old, new in replacements.items():
                    if old in text:
                        # Get coordinates and styling
                        x, y = span["bbox"][:2]
                        area = fitz.Rect(span["bbox"])
                        fontname = span["font"]
                        fontsize = span["size"]
                        color = span["color"]

                        # Step 1: Redact (cover old text with white)
                        page.add_redact_annot(area, fill=(1, 1, 1))
                        page.apply_redactions()

                        # Step 2: Insert new text at same position with same style
                        page.insert_text((x, y), new,
                                         fontname=fontname,
                                         fontsize=fontsize,
                                         color=color)

# Save output
doc.save("Updated_Report_July_2025.pdf")
print("✅ PDF updated and saved as 'Updated_Report_July_2025.pdf'")

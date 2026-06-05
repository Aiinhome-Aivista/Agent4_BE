import fitz
from docx import Document


class DocumentParser:

    @staticmethod
    def parse_pdf(path: str):

        text = ""

        pdf = fitz.open(path)

        for page in pdf:
            text += page.get_text()

        return text

    @staticmethod
    def parse_docx(path: str):

        doc = Document(path)

        return "\n".join(
            para.text
            for para in doc.paragraphs
        )

    @staticmethod
    def extract_text(path: str):

        if path.endswith(".pdf"):
            return DocumentParser.parse_pdf(path)

        if path.endswith(".docx"):
            return DocumentParser.parse_docx(path)

        raise Exception("Unsupported file format")
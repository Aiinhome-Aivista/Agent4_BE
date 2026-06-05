from services.ai.mistral_service import MistralService
import os


class DocumentSummaryService:

    @staticmethod
    def generate_summary(text: str, source_file: str = None):
        file_type = (
    os.path.splitext(source_file)[1].replace(".", "")
    if source_file else "unknown"
)

        prompt = f"""
        You are an advanced AI Document Understanding and Summarization Assistant.

        Your task is to carefully read and deeply understand the uploaded document content.

        Generate a clean, natural, human-readable summary that explains:

        - what the document is about
        - the purpose of the document
        - the major systems, services, or topics discussed
        - the operational/business context
        - important technical or functional details
        - overall meaning of the document

        IMPORTANT INSTRUCTIONS:

        1. The summary MUST be grammatically correct and professionally written.

        2. The summary MUST be easy to understand even for NON-TECHNICAL users.

        3. Avoid overly complex technical jargon unless necessary.

        4. If technical terms exist, explain them naturally in simple language.

        5. Write the summary like a human analyst explaining the document to another person.

        6. Maintain strong contextual understanding.
        Do NOT generate generic summaries.

        7. Infer the actual purpose of the document from context.

        8. If the document contains:
        - logs
        - incidents
        - APIs
        - infrastructure
        - code
        - architecture
        - configurations
        - cloud systems
        - deployment details
        - monitoring data
        - enterprise workflows

        then explain their role in simple understandable language.

        9. Make the summary cohesive and narrative-driven,
        NOT bullet-point dumping.

        10. Do NOT hallucinate information.
        Only summarize based on provided content.

        11. If the document is incomplete or unclear,
        mention that naturally.

        12. Return ONLY valid JSON.

        STRICT OUTPUT FORMAT:

        {{
        "summary": "A well-written contextual summary of the document in natural language."
        }}

        RULES:
        - DO NOT return markdown
        - DO NOT return explanations
        - DO NOT wrap response in triple backticks
        - DO NOT include additional keys
        - ONLY return valid JSON

        DOCUMENT CONTENT:
        {text[:15000]}
        """


        import json

        result = MistralService.analyze_incident(prompt)

        print("MISTRAL RAW RESPONSE =", result)

        try:

            # if response is string
            if isinstance(result, str):
                result = json.loads(result)

            return {
                "source_file": source_file,
                "file_type": file_type,
                "summary": result.get(
                    "summary",
                    "No summary generated"
                )
            }

        except Exception as e:

            print("SUMMARY JSON PARSE ERROR =", e)

            return {
                "source_file": source_file,
                "file_type": file_type,
                "summary": str(result)
            }
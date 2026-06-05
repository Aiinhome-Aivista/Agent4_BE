from database.db_connection import get_db_connection

from services.documents.document_parser import DocumentParser
from services.documents.document_summary_service import DocumentSummaryService
from services.documents.vector_store_service import VectorStoreService
from services.documents.knowledge_graph_service import KnowledgeGraphService
from services.documents.arangodb_service import ArangoDBService


class DocumentProcessor:

    @staticmethod
    def process_document(
        filename: str,
        file_path: str
    ):

        extracted_text = DocumentParser.extract_text(
            file_path
        )

        summary_response = (
            DocumentSummaryService.generate_summary(
                extracted_text,
                filename
            )
        )

        raw_summary = summary_response.get(
            "summary",
            "No summary generated"
        )

        file_type = summary_response.get(
            "file_type",
            "unknown"
        )

        print("RAW SUMMARY TYPE =", type(raw_summary))
        print("RAW SUMMARY =", raw_summary)

        graph_data = (
            KnowledgeGraphService.generate_graph(
                extracted_text,
                filename
            )
        )

        graph_url = graph_data.get(
            "graph_url",
            None
        )

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO uploaded_documents
            (
                filename,
                file_path,
                raw_summary,
                file_type,
                graph_url
            )
            VALUES (%s,%s,%s,%s,%s)
        """, (
            filename,
            file_path,
            raw_summary,
            file_type,
            graph_url
        ))

        conn.commit()

        document_id = cursor.lastrowid

        cursor.close()
        conn.close()

        VectorStoreService.store_document(
            document_id=document_id,
            filename=filename,
            text=extracted_text,
            summary=raw_summary
        )

        graph_data = (
            KnowledgeGraphService.generate_graph(
                extracted_text,
                filename
            )
        )

        graph_url = graph_data.get(
            "graph_url",
            None
        )

        ArangoDBService.store_graph(
            graph_data
        )

        return {
            "document_id": document_id,
            "filename": filename,
            "file_type": file_type,
            "raw_summary": raw_summary,
            "graph_url": graph_url,
            "knowledge_graph": graph_data
        }

    @staticmethod
    def get_document_by_id(document_id: int):
        """Retrieve a single document by ID from database."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                id,
                filename,
                raw_summary,
                graph_url,
                file_type,
                uploaded_at
            FROM uploaded_documents
            WHERE id = %s
        """, (document_id,))
        
        document = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return document   

    @staticmethod
    def get_all_documents():
        """Retrieve all uploaded documents."""

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                filename,
                file_path,
                raw_summary,
                graph_url,
                file_type,
                uploaded_at
            FROM uploaded_documents
            ORDER BY id DESC
        """)

        documents = cursor.fetchall()

        cursor.close()
        conn.close()

        return documents     
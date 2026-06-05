import os
import chromadb

from services.ai.embedding_service import EmbeddingService


class VectorStoreService:

    _client = None
    _collection = None

    @classmethod
    def get_client(cls):

        if cls._client is None:

            os.makedirs("./chromadb_data", exist_ok=True)

            cls._client = chromadb.PersistentClient(
                path="./chromadb_data"
            )

        return cls._client

    @classmethod
    def get_collection(cls):

        if cls._collection is None:

            client = cls.get_client()

            cls._collection = client.get_or_create_collection(
                name="documents_collection"
            )

        return cls._collection

    @staticmethod
    def store_document(
        document_id: int,
        filename: str,
        text: str,
        summary: str
    ):

        collection = VectorStoreService.get_collection()

        embedding = EmbeddingService.generate_embedding(
            text[:5000]
        )

        collection.upsert(
            ids=[str(document_id)],
            documents=[text],
            embeddings=[embedding],
            metadatas=[{
                "document_id": document_id,
                "filename": filename,
                "summary": summary
            }]
        )
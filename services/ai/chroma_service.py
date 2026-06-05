# import os
# import chromadb
# from chromadb.config import Settings
# from services.ai.embedding_service import EmbeddingService

# CHROMADB_PATH = os.getenv("CHROMADB_PATH", "./chromadb_storage")

# client = chromadb.PersistentClient(path=CHROMADB_PATH)

# collection = client.get_or_create_collection(
#     name="incidents"
# )


# class ChromaService:

#     @staticmethod
#     def store_incident(incident_id: str, text: str, metadata: dict):

#         embedding = EmbeddingService.generate_embedding(text)

#         collection.upsert(
#             ids=[incident_id],
#             documents=[text],
#             metadatas=[metadata],
#             embeddings=[embedding]
#         )

#     @staticmethod
#     def search_similar(text: str, top_k: int = 3):

#         embedding = EmbeddingService.generate_embedding(text)

#         return collection.query(
#             query_embeddings=[embedding],
#             n_results=top_k
#         )

import os
import chromadb
from chromadb.config import Settings
from services.ai.embedding_service import EmbeddingService

CHROMADB_PATH = os.getenv("CHROMADB_PATH", "./chromadb_storage")

client = chromadb.PersistentClient(path=CHROMADB_PATH)

collection = client.get_or_create_collection(
    name="incidents"
)


class ChromaService:

    @staticmethod
    def store_incident(incident_id: str, text: str, metadata: dict):
        """
        Store an incident embedding in ChromaDB.
        Always ensures 'incident_id' is present in metadata for scoped retrieval.
        """
        embedding = EmbeddingService.generate_embedding(text)

        # Ensure incident_id is always in metadata for filtered RAG chat
        enriched_metadata = {**metadata, "incident_id": incident_id}

        collection.upsert(
            ids=[incident_id],
            documents=[text],
            metadatas=[enriched_metadata],
            embeddings=[embedding]
        )

    @staticmethod
    def search_similar(text: str, top_k: int = 3):
        """Global similarity search across all incidents."""
        embedding = EmbeddingService.generate_embedding(text)

        return collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )

    @staticmethod
    def search_by_incident_id(incident_id: str, query_text: str, top_k: int = 5):
        """
        Scoped similarity search filtered to a specific incident_id.
        Used for RAG chat guardrail — only retrieves context for the selected incident.
        Returns list of document strings, or empty list if none found.
        """
        embedding = EmbeddingService.generate_embedding(query_text)

        try:
            results = collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where={"incident_id": incident_id}
            )
            docs = results.get("documents", [[]])[0]
            return docs if docs else []
        except Exception:
            # If filter returns nothing or collection is empty, return empty
            return []

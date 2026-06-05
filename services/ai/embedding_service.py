from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")


class EmbeddingService:

    @staticmethod
    def generate_embedding(text: str):
        return _model.encode(text).tolist()
"""Real local embeddings; errors propagate without mock fallback."""
from sentence_transformers import SentenceTransformer

MODEL_REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'

class MyEmbedder:
    def __init__(self, model_name, cache_folder=None):
        self.model_name = model_name
        self.revision = MODEL_REVISION
        self.model = SentenceTransformer(model_name, revision=self.revision,
                                         cache_folder=cache_folder, device='cpu')
        self.dimensions = self.model.get_sentence_embedding_dimension()

    def embed_documents(self, texts):
        return self.model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=True).tolist()

    def embed_query(self, question):
        return self.model.encode(question, normalize_embeddings=True).tolist()

import threading


class Embedder:
    def __init__(self, model_name):
        self.model_name = model_name
        self.model = None
        self.lock = threading.Lock()

    def _get_model(self):
        if self.model is None:
            with self.lock:
                if self.model is None:
                    from sentence_transformers import SentenceTransformer
                    self.model = SentenceTransformer(self.model_name)
        return self.model

    def build_text(self, record):
        from ..core.utils import EXT_WORDS
        parts = [
            record["name"],
            record.get("parent_folder", ""),
            EXT_WORDS.get(record.get("extension", ""), ""),
            record.get("category", ""),
        ]
        return " ".join(p for p in parts if p)

    def embed_texts(self, texts, batch_size=64, show_progress=False):
        import numpy as np
        model = self._get_model()
        dense = model.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return np.asarray(dense, dtype="float32")

    def embed_query(self, query_text):
        import numpy as np
        model = self._get_model()
        dense = model.encode(
            [query_text],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return np.asarray(dense, dtype="float32")

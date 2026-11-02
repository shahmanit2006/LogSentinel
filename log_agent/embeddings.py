from sentence_transformers import SentenceTransformer

_MODEL = None
_MODEL_NAME = None

def get_model(model_name):
    global _MODEL, _MODEL_NAME
    if _MODEL is None or _MODEL_NAME != model_name:
        _MODEL = SentenceTransformer(model_name)
        _MODEL_NAME = model_name
    return _MODEL

def encode_texts(texts, model_name):
    model = get_model(model_name)
    vectors = model.encode(
        [str(x) for x in texts],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False
    )
    return vectors.astype("float32")

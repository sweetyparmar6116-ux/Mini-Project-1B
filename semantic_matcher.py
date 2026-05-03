from sentence_transformers import SentenceTransformer, util

# Load model ONCE (important for performance)
model = SentenceTransformer("all-MiniLM-L6-v2")

def sbert_similarity(text1, text2):
    """
    Returns semantic similarity score (0–100)
    using SBERT embeddings + cosine similarity
    """

    if not text1.strip() or not text2.strip():
        return 0.0

    emb1 = model.encode(text1, convert_to_tensor=True)
    emb2 = model.encode(text2, convert_to_tensor=True)

    score = util.cos_sim(emb1, emb2).item()
    return round(score * 100, 2)

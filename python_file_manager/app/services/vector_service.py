import uuid

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models

from app.config import settings


# Initialize embedding model
embedding_model = SentenceTransformer(
    settings.embedding_model
)

# Initialize Qdrant
qdrant = QdrantClient(
    url=settings.qdrant_url
)

COLLECTION = settings.qdrant_collection

VECTOR_SIZE = 384


def create_collection():

    if not qdrant.collection_exists(COLLECTION):

        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE
            )
        )


def split_code(code: str, chunk_size=60, overlap=10):

    lines = code.splitlines()

    chunks = []

    start = 0

    while start < len(lines):

        end = start + chunk_size

        chunk = "\n".join(lines[start:end])

        if chunk.strip():
            chunks.append({
                "content": chunk,
                "start_line": start + 1,
                "end_line": min(end, len(lines))
            })

        start += chunk_size - overlap

    return chunks


def store_code_vectors(
    file_id: str,
    filename: str,
    code: str
):

    chunks = split_code(code)

    if not chunks:
        return 0

    texts = [chunk["content"] for chunk in chunks]

    vectors = embedding_model.encode(
        texts,
        normalize_embeddings=True
    ).tolist()

    points = []

    for chunk, vector in zip(chunks, vectors):

        points.append(
            models.PointStruct(
                id=str(uuid.uuid4()),

                vector=vector,

                payload={
                    "file_id": file_id,
                    "filename": filename,
                    "content": chunk["content"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"]
                }
            )
        )

    qdrant.upsert(
        collection_name=COLLECTION,
        points=points,
        wait=True
    )

    return len(points)


def search_code(query: str, limit: int = 5):

    query_vector = embedding_model.encode(
        query,
        normalize_embeddings=True
    ).tolist()

    results = qdrant.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=limit,
        with_payload=True
    )

    return results.points
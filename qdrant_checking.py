
import os
import uuid
import argparse
import fitz

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models


# Configuration
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "pdf_documents"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
BATCH_SIZE = 64


# Initialize clients
print("Loading embedding model...")

embedding_model = SentenceTransformer(EMBEDDING_MODEL)

client = QdrantClient(url=QDRANT_URL)

VECTOR_SIZE = embedding_model.get_sentence_embedding_dimension()


def create_collection():

    if not client.collection_exists(COLLECTION_NAME):

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE
            )
        )

        print(f"Collection created: {COLLECTION_NAME}")

    else:
        print(f"Collection already exists: {COLLECTION_NAME}")


def extract_pdf(pdf_path):

    document = fitz.open(pdf_path)

    pages = []

    for page_number, page in enumerate(document):

        text = page.get_text("text").strip()

        if text:
            pages.append({
                "text": text,
                "page": page_number + 1
            })

    document.close()

    return pages


def split_text(text, chunk_size=CHUNK_SIZE,
               overlap=CHUNK_OVERLAP):

    words = text.split()

    chunks = []

    start = 0

    while start < len(words):

        end = start + chunk_size

        chunk = " ".join(words[start:end])

        if chunk.strip():
            chunks.append(chunk)

        if end >= len(words):
            break

        start = end - overlap

    return chunks


def process_pdf(pdf_path, organization_id="default"):

    filename = os.path.basename(pdf_path)

    print(f"\nProcessing: {filename}")

    pages = extract_pdf(pdf_path)

    points = []

    document_id = str(uuid.uuid4())

    for page_data in pages:

        chunks = split_text(page_data["text"])

        for chunk_index, chunk in enumerate(chunks):

            points.append({
                "id": str(uuid.uuid4()),
                "text": chunk,
                "page": page_data["page"],
                "chunk_index": chunk_index
            })

    print(f"Extracted {len(points)} chunks")

    # Store in batches
    for i in range(0, len(points), BATCH_SIZE):

        batch = points[i:i + BATCH_SIZE]

        texts = [item["text"] for item in batch]

        embeddings = embedding_model.encode(
            texts,
            normalize_embeddings=True
        ).tolist()

        qdrant_points = []

        for item, embedding in zip(batch, embeddings):

            qdrant_points.append(
                models.PointStruct(
                    id=item["id"],
                    vector=embedding,
                    payload={
                        "document_id": document_id,
                        "organization_id": organization_id,
                        "filename": filename,
                        "page": item["page"],
                        "chunk_index": item["chunk_index"],
                        "text": item["text"]
                    }
                )
            )

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=qdrant_points,
            wait=True
        )

        print(
            f"Uploaded {min(i + BATCH_SIZE, len(points))}"
            f"/{len(points)} chunks"
        )

    print(f"Successfully stored: {filename}")

    return document_id


def search_documents(question, top_k=5):

    query_vector = embedding_model.encode(
        question,
        normalize_embeddings=True
    ).tolist()

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True
    ).points

    for result in results:

        payload = result.payload

        print("\n" + "=" * 60)

        print(f"File: {payload['filename']}")
        print(f"Page: {payload['page']}")
        print(f"Score: {result.score:.4f}")

        print(f"Content:\n{payload['text']}")


def main():

    parser = argparse.ArgumentParser(
        description="Store PDF documents in Qdrant"
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to PDF file"
    )

    parser.add_argument(
        "--organization",
        default="default"
    )

    parser.add_argument(
        "--search",
        help="Optional semantic search query"
    )

    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        raise FileNotFoundError(args.pdf)

    create_collection()

    document_id = process_pdf(
        args.pdf,
        args.organization
    )

    print(f"\nDocument ID: {document_id}")

    if args.search:
        search_documents(args.search)


if __name__ == "__main__":
    main()

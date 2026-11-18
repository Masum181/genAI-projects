
import os
import argparse

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from openai import OpenAI


# ==================================
# 1. CONFIGURATION
# ==================================

load_dotenv()

QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://localhost:6333"
)

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None

COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION",
    "pdf_documents"
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini"
)

EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

TOP_K = 5


# ==================================
# 2. INITIALIZE CLIENTS
# ==================================

print("Loading embedding model...")

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL
)

qdrant = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
)

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing!")

llm = OpenAI(
    api_key=OPENAI_API_KEY
)


# ==================================
# 3. GENERATE QUESTION EMBEDDING
# ==================================

def generate_embedding(text: str):

    vector = embedding_model.encode(
        text,
        normalize_embeddings=True
    )

    return vector.tolist()


# ==================================
# 4. RETRIEVE DOCUMENTS FROM QDRANT
# ==================================

def retrieve_documents(
    question: str,
    top_k: int = TOP_K,
    organization_id: str = "default"
):

    query_vector = generate_embedding(question)

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,

        query=query_vector,

        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="organization_id",
                    match=models.MatchValue(
                        value=organization_id
                    )
                )
            ]
        ),

        limit=top_k,

        with_payload=True
    ).points

    documents = []

    for result in results:

        payload = result.payload or {}

        documents.append({
            "text": payload.get("text", ""),
            "filename": payload.get("filename", "Unknown"),
            "page": payload.get("page"),
            "score": result.score,
            "document_id": payload.get("document_id")
        })

    return documents


# ==================================
# 5. BUILD CONTEXT
# ==================================

def build_context(documents):

    context_parts = []

    for index, doc in enumerate(documents, start=1):

        context_parts.append(
            f"""
            Source {index}
            Filename: {doc['filename']}
            Page: {doc['page']}

            Content:
            {doc['text']}
            """
        )

    return "\n\n".join(context_parts)


# ==================================
# 6. GENERATE ANSWER USING LLM
# ==================================

def generate_answer(question, documents):

    if not documents:
        return "No relevant documents were found.", []

    context = build_context(documents)

    response = llm.chat.completions.create(

        model=OPENAI_MODEL,

        messages=[
            {
                "role": "system",
                "content": """
                You are an intelligent document-based
                question answering assistant.

                Answer using ONLY the provided context.

                Rules:
                1. Do not invent information.
                2. If the answer is not in the context,
                   say you cannot find the answer.
                3. Provide clear and concise answers.
                4. Mention relevant source filenames
                   and page numbers.
                """
            },
            {
                "role": "user",
                "content": f"""
                Context:
                {context}

                Question:
                {question}

                Answer:
                """
            }
        ],

        temperature=0.2
    )

    answer = response.choices[0].message.content

    return answer, documents


# ==================================
# 7. COMPLETE RAG PIPELINE
# ==================================

def rag_query(
    question: str,
    organization_id: str = "default"
):

    print("\nSearching Qdrant...")

    documents = retrieve_documents(
        question=question,
        organization_id=organization_id
    )

    if not documents:
        return {
            "answer": "No relevant documents found.",
            "sources": []
        }

    print(f"Retrieved {len(documents)} chunks.")

    answer, sources = generate_answer(
        question,
        documents
    )

    return {
        "answer": answer,
        "sources": sources
    }


# ==================================
# 8. COMMAND LINE INTERFACE
# ==================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Ask questions using Qdrant RAG"
    )

    parser.add_argument(
        "--question",
        required=True,
        help="Your question"
    )

    parser.add_argument(
        "--organization",
        default="default"
    )

    args = parser.parse_args()

    result = rag_query(
        question=args.question,
        organization_id=args.organization
    )

    print("\n" + "=" * 60)

    print("ANSWER:")
    print(result["answer"])

    print("\nSOURCES:")

    for source in result["sources"]:

        print(
            f"- {source['filename']} "
            f"(Page {source['page']}, "
            f"Score: {source['score']:.4f})"
        )

    print("=" * 60)

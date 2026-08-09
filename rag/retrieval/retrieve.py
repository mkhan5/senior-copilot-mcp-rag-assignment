import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from google import genai
from dotenv import load_dotenv

load_dotenv()


@dataclass
class RetrievalResult:
    content: str
    metadata: Dict[str, Any]
    score: float
    citation_id: str


@dataclass
class GroundedAnswer:
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float
    query: str


class RetrievalService:
    def __init__(
        self,
        persist_dir: str = "rag/chroma_db",
        collection_name: str = "maintenance_docs",
        embedding_model: str = "all-MiniLM-L6-v2",
        gemini_model: str = "gemini-2.5-flash",
        top_k: int = 5,
        score_threshold: float = 0.3,
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.top_k = top_k
        self.score_threshold = score_threshold

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        self.collection = self.client.get_collection(name=collection_name)
        self.embedder = SentenceTransformer(embedding_model)

        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai_client = genai.Client(api_key=api_key)
            self.gemini_client = genai_client
            self.gemini_model = "gemini-2.5-flash"
        else:
            self.gemini_client = None
            self.gemini_model = None

    def retrieve(
        self,
        query: str,
        asset_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        query_embedding = self.embedder.encode([query]).tolist()[0]

        where_filter = {}
        if asset_id:
            where_filter["asset_id"] = asset_id
        if doc_type:
            where_filter["doc_type"] = doc_type

        k = top_k or self.top_k
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )

        retrieval_results = []
        if results["documents"] and results["documents"][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                score = 1 - distance
                if score >= self.score_threshold:
                    citation_id = f"[{i+1}]"
                    retrieval_results.append(
                        RetrievalResult(
                            content=doc,
                            metadata=metadata,
                            score=score,
                            citation_id=citation_id,
                        )
                    )

        return retrieval_results

    def _build_context(self, results: List[RetrievalResult]) -> str:
        context_parts = []
        for r in results:
            source = r.metadata.get("source", "unknown")
            asset = r.metadata.get("asset_name") or r.metadata.get("asset_id") or "unknown"
            doc_type = r.metadata.get("doc_type", "unknown")
            context_parts.append(
                f"{r.citation_id} Source: {source} | Asset: {asset} | Type: {doc_type}\n{r.content}"
            )
        return "\n\n---\n\n".join(context_parts)

    def _build_citations(self, results: List[RetrievalResult]) -> List[Dict[str, Any]]:
        citations = []
        for r in results:
            citations.append({
                "citation_id": r.citation_id,
                "source": r.metadata.get("source", "unknown"),
                "asset_id": r.metadata.get("asset_id"),
                "asset_name": r.metadata.get("asset_name"),
                "doc_type": r.metadata.get("doc_type"),
                "score": round(r.score, 3),
                "chunk_index": r.metadata.get("chunk_index"),
            })
        return citations

    def _check_prompt_injection(self, content: str) -> bool:
        injection_patterns = [
            "ignore previous instructions",
            "ignore all instructions",
            "system prompt",
            "you are now",
            "pretend to be",
            "roleplay",
            "disregard",
            "override",
            "new instructions",
        ]
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in injection_patterns)

    def generate_answer(self, query: str, results: List[RetrievalResult]) -> GroundedAnswer:
        if not results:
            return GroundedAnswer(
                answer="I could not find relevant information in the maintenance documents to answer your question.",
                citations=[],
                confidence=0.0,
                query=query,
            )

        for r in results:
            if self._check_prompt_injection(r.content):
                print(f"Warning: Potential prompt injection detected in chunk from {r.metadata.get('source')}")

        context = self._build_context(results)
        citations = self._build_citations(results)

        if not self.gemini_client:
            answer = "Based on the retrieved documents:\n\n" + context[:2000]
            return GroundedAnswer(
                answer=answer,
                citations=citations,
                confidence=0.5,
                query=query,
            )

        prompt = f"""You are a maintenance engineering assistant. Answer the user's question using ONLY the provided context from maintenance documents.

Context:
{context}

Question: {query}

Instructions:
1. Answer based ONLY on the provided context
2. Cite sources using the citation IDs like [1], [2], etc.
3. If the context doesn't contain enough information, say so clearly
4. Do not add information not in the context
5. Be concise and specific
6. Include actionable recommendations when applicable

Answer:"""

        try:
            response = self.gemini_client.models.generate_content(model=self.gemini_model, contents=prompt)
            answer = response.text

            avg_score = sum(r.score for r in results) / len(results)
            confidence = min(avg_score * 1.2, 1.0)

            return GroundedAnswer(
                answer=answer,
                citations=citations,
                confidence=confidence,
                query=query,
            )
        except Exception as e:
            return GroundedAnswer(
                answer=f"Error generating answer: {str(e)}. Retrieved context:\n{context[:1500]}",
                citations=citations,
                confidence=0.3,
                query=query,
            )

    def query(self, query: str, asset_id: Optional[str] = None, doc_type: Optional[str] = None) -> GroundedAnswer:
        results = self.retrieve(query, asset_id=asset_id, doc_type=doc_type)
        return self.generate_answer(query, results)


def main():
    service = RetrievalService()
    test_queries = [
        "What are the alarm response procedures for high discharge pressure on Boiler Feed Pump 101?",
        "What is the maintenance schedule for Compressor 201?",
        "What are the critical spare parts for pumps?",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        result = service.query(query)
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Answer: {result.answer[:500]}...")
        print(f"Citations: {len(result.citations)}")


if __name__ == "__main__":
    main()
import os
import json
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import markdown


class DocumentIngestion:
    def __init__(
        self,
        documents_dir: str = None,
        persist_dir: str = None,
        collection_name: str = "maintenance_docs",
        embedding_model: str = "all-MiniLM-L6-v2",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        import os
        self.documents_dir = Path(documents_dir or os.getenv("DOCUMENTS_DIR", "rag/documents"))
        self.persist_dir = Path(persist_dir or os.getenv("PERSIST_DIR", "rag/chroma_db"))
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        self.embedder = SentenceTransformer(embedding_model)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
        )

    def extract_metadata(self, file_path: Path, content: str) -> Dict[str, Any]:
        asset_id = None
        asset_name = None
        doc_type = "general"

        lines = content.split("\n")
        for line in lines[:20]:
            if "asset_id" in line.lower() or "asset id" in line.lower():
                parts = line.split(":")
                if len(parts) > 1:
                    asset_id = parts[1].strip().strip("*` ")
            if "asset_name" in line.lower() or "asset name" in line.lower():
                parts = line.split(":")
                if len(parts) > 1:
                    asset_name = parts[1].strip().strip("*` ")

        filename = file_path.stem.lower()
        if "manual" in filename:
            doc_type = "equipment_manual"
        elif "procedure" in filename or "sop" in filename:
            doc_type = "maintenance_procedure"
        elif "checklist" in filename:
            doc_type = "inspection_checklist"
        elif "spare" in filename:
            doc_type = "spare_parts_guidance"
        elif "troubleshoot" in filename:
            doc_type = "troubleshooting_guide"

        return {
            "source": file_path.name,
            "asset_id": asset_id or "",
            "asset_name": asset_name or "",
            "doc_type": doc_type,
            "file_path": str(file_path),
        }

    def load_document(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix == ".md":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        elif suffix == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        elif suffix == ".pdf":
            import pypdf
            text = ""
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def chunk_document(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks = self.splitter.split_text(content)
        result = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy()
            # Convert all values to strings for ChromaDB compatibility
            for key, value in chunk_metadata.items():
                if value is None:
                    chunk_metadata[key] = ""
                elif not isinstance(value, (str, int, float, bool)):
                    chunk_metadata[key] = str(value)
            chunk_metadata["chunk_index"] = str(i)
            chunk_metadata["chunk_count"] = str(len(chunks))
            result.append({"content": chunk, "metadata": chunk_metadata})
        return result

    def ingest(self) -> Dict[str, Any]:
        files = list(self.documents_dir.glob("*.md")) + list(self.documents_dir.glob("*.txt")) + list(self.documents_dir.glob("*.pdf"))
        if not files:
            return {"status": "no_documents", "count": 0}

        all_chunks = []
        all_metadatas = []
        all_ids = []

        for file_path in files:
            try:
                content = self.load_document(file_path)
                if not content.strip():
                    continue

                metadata = self.extract_metadata(file_path, content)
                chunks = self.chunk_document(content, metadata)

                for chunk in chunks:
                    chunk_id = f"{file_path.stem}_{chunk['metadata']['chunk_index']}"
                    all_ids.append(chunk_id)
                    all_chunks.append(chunk["content"])
                    all_metadatas.append(chunk["metadata"])

            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue

        if not all_chunks:
            return {"status": "no_chunks", "count": 0}

        embeddings = self.embedder.encode(all_chunks, show_progress_bar=True).tolist()

        self.collection.add(
            ids=all_ids,
            documents=all_chunks,
            embeddings=embeddings,
            metadatas=all_metadatas,
        )

        return {
            "status": "success",
            "documents_processed": len(files),
            "chunks_created": len(all_chunks),
            "collection": self.collection_name,
        }


def main():
    ingestion = DocumentIngestion()
    result = ingestion.ingest()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
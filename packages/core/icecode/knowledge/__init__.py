"""ICECODE Knowledge Base — local RAG with sentence-transformers + FAISS."""
from .manager import KnowledgeManager
from .indexer import DocumentIndexer
from .store import VectorStore
from .retriever import RAGRetriever

__all__ = ["KnowledgeManager", "DocumentIndexer", "VectorStore", "RAGRetriever"]

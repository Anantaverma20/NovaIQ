"""
Vector store service with optional ChromaDB support.

If OpenAI API key is not configured, all operations become no-ops.
This allows the application to run without vector capabilities.
"""
from typing import Optional, Any
import hashlib
from datetime import datetime

from app.config import get_settings
from app.deps import get_chroma_collection, get_openai_client


class VectorStoreDisabled(Exception):
    """Raised when attempting vector operations without proper configuration."""
    pass


def is_enabled() -> bool:
    """Check if vector operations are available."""
    settings = get_settings()
    return settings.vectors_enabled


def _generate_doc_id(text: str, metadata: dict[str, Any]) -> str:
    """
    Generate deterministic document ID from content.
    
    This ensures idempotent ingestion - same content = same ID.
    """
    # Create hash from text + key metadata
    content = f"{text}:{metadata.get('url', '')}:{metadata.get('title', '')}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


async def add_documents(
    texts: list[str],
    metadatas: Optional[list[dict[str, Any]]] = None,
    *,
    batch_size: int = 100
) -> dict[str, Any]:
    """
    Add documents to vector store with embeddings.
    
    This operation is idempotent - same documents won't be duplicated.
    
    Args:
        texts: List of document texts to embed
        metadatas: Optional metadata for each document
        batch_size: Number of documents to process at once
    
    Returns:
        Stats dict with counts of added/skipped documents
        
    Raises:
        VectorStoreDisabled: If vectors not configured (can be caught and ignored)
    """
    if not is_enabled():
        return {
            "status": "disabled",
            "added": 0,
            "skipped": len(texts),
            "message": "Vector operations disabled - OPENAI_API_KEY not configured"
        }
    
    collection = get_chroma_collection()
    if not collection:
        return {
            "status": "unavailable",
            "added": 0,
            "skipped": len(texts),
            "message": "ChromaDB not available"
        }
    
    if not texts:
        return {"status": "success", "added": 0, "skipped": 0}
    
    # Prepare metadata
    if metadatas is None:
        metadatas = [{}] * len(texts)
    
    # Add timestamp to metadata
    for meta in metadatas:
        if "indexed_at" not in meta:
            meta["indexed_at"] = datetime.utcnow().isoformat()
    
    # Generate deterministic IDs
    ids = [_generate_doc_id(text, meta) for text, meta in zip(texts, metadatas)]
    
    # Check which documents already exist
    try:
        existing = collection.get(ids=ids)
        existing_ids = set(existing.get("ids", []))
        
        # Filter to only new documents
        new_texts = []
        new_metadatas = []
        new_ids = []
        
        for text, meta, doc_id in zip(texts, metadatas, ids):
            if doc_id not in existing_ids:
                new_texts.append(text)
                new_metadatas.append(meta)
                new_ids.append(doc_id)
        
        # Add new documents in batches
        added = 0
        for i in range(0, len(new_texts), batch_size):
            batch_texts = new_texts[i:i + batch_size]
            batch_metadatas = new_metadatas[i:i + batch_size]
            batch_ids = new_ids[i:i + batch_size]
            
            collection.add(
                documents=batch_texts,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
            added += len(batch_ids)
        
        return {
            "status": "success",
            "added": added,
            "skipped": len(texts) - added,
            "total": len(texts)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "added": 0,
            "skipped": len(texts),
            "error": str(e)
        }


async def query_documents(
    query_text: str,
    *,
    n_results: int = 5,
    where: Optional[dict[str, Any]] = None
) -> list[dict[str, Any]]:
    """
    Semantic search for relevant documents.
    
    Args:
        query_text: Natural language search query
        n_results: Number of results to return
        where: Optional metadata filters
    
    Returns:
        List of documents with keys: id, text, metadata, distance
        Empty list if vectors disabled
    """
    if not is_enabled():
        return []
    
    collection = get_chroma_collection()
    if not collection:
        return []
    
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where
        )
        
        # Format results
        documents = []
        if results.get("documents"):
            for i in range(len(results["documents"][0])):
                doc = {
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                }
                documents.append(doc)
        
        return documents
        
    except Exception as e:
        print(f"Vector query error: {e}")
        return []


async def get_document_by_id(doc_id: str) -> Optional[dict[str, Any]]:
    """
    Retrieve a specific document by ID.
    
    Args:
        doc_id: Document ID
    
    Returns:
        Document dict or None if not found
    """
    if not is_enabled():
        return None
    
    collection = get_chroma_collection()
    if not collection:
        return None
    
    try:
        result = collection.get(ids=[doc_id])
        if result.get("ids"):
            return {
                "id": result["ids"][0],
                "text": result["documents"][0],
                "metadata": result["metadatas"][0] if result.get("metadatas") else {},
            }
        return None
    except Exception:
        return None


async def delete_documents(doc_ids: list[str]) -> dict[str, Any]:
    """
    Delete documents from vector store.
    
    Args:
        doc_ids: List of document IDs to delete
    
    Returns:
        Stats dict with deletion count
    """
    if not is_enabled():
        return {"status": "disabled", "deleted": 0}
    
    collection = get_chroma_collection()
    if not collection:
        return {"status": "unavailable", "deleted": 0}
    
    try:
        collection.delete(ids=doc_ids)
        return {"status": "success", "deleted": len(doc_ids)}
    except Exception as e:
        return {"status": "error", "deleted": 0, "error": str(e)}


async def count_documents() -> int:
    """
    Get total count of documents in vector store.
    
    Returns:
        Document count, or 0 if vectors disabled
    """
    if not is_enabled():
        return 0
    
    collection = get_chroma_collection()
    if not collection:
        return 0
    
    try:
        return collection.count()
    except Exception:
        return 0


async def clear_all() -> dict[str, Any]:
    """
    Clear all documents from vector store.
    
    ⚠️ WARNING: This is a destructive operation.
    
    Returns:
        Status dict
    """
    if not is_enabled():
        return {"status": "disabled", "cleared": 0}
    
    collection = get_chroma_collection()
    if not collection:
        return {"status": "unavailable", "cleared": 0}
    
    try:
        # Get all IDs and delete them
        result = collection.get()
        if result.get("ids"):
            collection.delete(ids=result["ids"])
            return {"status": "success", "cleared": len(result["ids"])}
        return {"status": "success", "cleared": 0}
    except Exception as e:
        return {"status": "error", "cleared": 0, "error": str(e)}

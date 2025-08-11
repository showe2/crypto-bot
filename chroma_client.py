import hashlib
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
    logger.debug("ChromaDB is available")
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.debug("ChromaDB not installed - service disabled")

from app.core.config import get_settings

settings = get_settings()


class ChromaClient:
    """ChromaDB client for vector storage and knowledge management"""
    
    def __init__(self):
        self._client = None
        self._collection = None
        self.db_path = Path(settings.CHROMA_DB_PATH)
        self.collection_name = settings.CHROMA_COLLECTION_NAME
        self._connected = False
    
    async def connect(self):
        """Initialize ChromaDB connection"""
        if not CHROMADB_AVAILABLE:
            logger.debug("ChromaDB not available - install with: pip install chromadb sentence-transformers")
            return
        
        try:
            # Ensure database directory exists
            self.db_path.mkdir(parents=True, exist_ok=True)
            
            # Clear any corrupted data first
            chroma_files = list(self.db_path.glob("*"))
            if chroma_files and any("chroma.sqlite3" in str(f) for f in chroma_files):
                logger.info("Found existing ChromaDB files, attempting clean initialization...")
                try:
                    # Try to remove corrupted files
                    for file in self.db_path.glob("chroma.sqlite3*"):
                        file.unlink()
                    logger.info("Cleaned corrupted ChromaDB files")
                except Exception as e:
                    logger.warning(f"Could not clean files: {e}")
            
            # Use the new ChromaDB client initialization (v0.4+)
            try:
                # Try new persistent client method
                self._client = chromadb.PersistentClient(path=str(self.db_path))
                logger.info("Using new ChromaDB PersistentClient")
            except Exception as e:
                logger.warning(f"PersistentClient failed: {e}, trying alternatives...")
                # Fallback to legacy method for older versions
                try:
                    # Legacy configuration - only if Settings available
                    from chromadb.config import Settings as ChromaSettings
                    chroma_settings = ChromaSettings(
                        chroma_db_impl="duckdb+parquet",
                        persist_directory=str(self.db_path),
                        anonymized_telemetry=False
                    )
                    self._client = chromadb.Client(chroma_settings)
                    logger.info("Using legacy ChromaDB Client")
                except Exception as e2:
                    logger.warning(f"Legacy client failed: {e2}, using in-memory client...")
                    # Most basic fallback - in-memory client
                    self._client = chromadb.Client()
                    logger.warning("Using in-memory ChromaDB client (data will not persist)")
            
            # Get or create collection with better error handling
            collection_created = False
            collection_attempts = [
                # Attempt 1: Simple collection without embedding function
                lambda: self._client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Solana token knowledge base"}
                ),
                # Attempt 2: Get existing collection
                lambda: self._client.get_collection(name=self.collection_name),
                # Attempt 3: Delete and recreate
                lambda: self._recreate_collection(),
                # Attempt 4: Use different collection name
                lambda: self._client.create_collection(
                    name=f"{self.collection_name}_backup",
                    metadata={"description": "Solana token knowledge base backup"}
                )
            ]
            
            for i, attempt in enumerate(collection_attempts):
                try:
                    logger.debug(f"Collection attempt {i+1}/4...")
                    self._collection = attempt()
                    
                    if i == 3:  # If we used backup name
                        self.collection_name = f"{self.collection_name}_backup"
                        logger.info(f"Using backup collection name: {self.collection_name}")
                    
                    logger.info(f"Collection ready: {self.collection_name}")
                    collection_created = True
                    break
                    
                except Exception as e:
                    logger.debug(f"Collection attempt {i+1} failed: {str(e)}")
                    if i == len(collection_attempts) - 1:
                        logger.error(f"All collection attempts failed. Last error: {str(e)}")
                        raise Exception(f"Could not create or access collection: {str(e)}")
            
            if not collection_created:
                raise Exception("Failed to create collection after all attempts")
            
            self._connected = True
            logger.info("ChromaDB connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {str(e)}")
            logger.info("Suggestions:")
            logger.info("  1. Clear database: rm -rf ./shared_data/chroma")
            logger.info("  2. Reinstall ChromaDB: pip uninstall chromadb && pip install chromadb==0.4.15")
            logger.info("  3. Check permissions on ./shared_data/chroma directory")
            self._client = None
            self._collection = None
            self._connected = False
    
    def _recreate_collection(self):
        """Helper method to delete and recreate collection"""
        try:
            # Try to delete existing collection
            self._client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted existing collection: {self.collection_name}")
        except Exception:
            pass  # Collection probably doesn't exist
        
        # Create new collection
        return self._client.create_collection(
            name=self.collection_name,
            metadata={"description": "Solana token knowledge base - recreated"}
        )
    
    def is_connected(self) -> bool:
        """Check if ChromaDB is connected"""
        return self._connected and CHROMADB_AVAILABLE and self._client is not None
    
    async def disconnect(self):
        """Close ChromaDB connection"""
        if self._client:
            try:
                # Try to persist data if method exists
                if hasattr(self._client, 'persist'):
                    self._client.persist()
                    logger.info("ChromaDB data persisted")
            except Exception as e:
                logger.warning(f"Error persisting ChromaDB data: {str(e)}")
        
        self._client = None
        self._collection = None
        self._connected = False
        logger.info("ChromaDB connection closed")
    
    def _generate_id(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Generate unique ID for document"""
        # Use content hash + timestamp for uniqueness
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        timestamp = str(int(datetime.utcnow().timestamp()))
        return f"{content_hash}_{timestamp}"
    
    async def add_document(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """Add document to knowledge base"""
        if not self.is_connected():
            await self.connect()
        
        if not self.is_connected():
            raise Exception("ChromaDB not available")
        
        try:
            if doc_id is None:
                doc_id = self._generate_id(content, metadata)
            
            # Prepare metadata
            doc_metadata = {
                "timestamp": datetime.utcnow().isoformat(),
                "content_type": "text",
                **(metadata or {})
            }
            
            # Add to collection
            self._collection.add(
                documents=[content],
                metadatas=[doc_metadata],
                ids=[doc_id]
            )
            
            logger.debug(f"Added document to ChromaDB: {doc_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error adding document to ChromaDB: {str(e)}")
            raise
    
    async def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search documents in knowledge base"""
        if not self.is_connected():
            await self.connect()
        
        if not self.is_connected():
            raise Exception("ChromaDB not available")
        
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            logger.debug(f"ChromaDB search query: '{query}' returned {len(results.get('documents', [[]])[0])} results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching ChromaDB: {str(e)}")
            raise
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        if not self.is_connected():
            await self.connect()
        
        if not self.is_connected():
            return {"error": "ChromaDB not available"}
        
        try:
            # Get collection count
            count = self._collection.count()
            
            stats = {
                "total_documents": count,
                "collection_name": self.collection_name,
                "db_path": str(self.db_path),
                "chromadb_version": chromadb.__version__ if hasattr(chromadb, '__version__') else "unknown"
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)}


# Global ChromaDB client instance
chroma_client = ChromaClient()


async def init_chroma():
    """Initialize ChromaDB connection"""
    if CHROMADB_AVAILABLE:
        await chroma_client.connect()
    else:
        logger.warning("ChromaDB initialization skipped - not installed")


async def close_chroma():
    """Close ChromaDB connection"""
    if CHROMADB_AVAILABLE:
        await chroma_client.disconnect()


async def get_chroma_client() -> ChromaClient:
    """Get ChromaDB client (dependency injection)"""
    if CHROMADB_AVAILABLE and not chroma_client.is_connected():
        await chroma_client.connect()
    return chroma_client


async def check_chroma_health() -> Dict[str, Any]:
    """Check ChromaDB health"""
    try:
        if not CHROMADB_AVAILABLE:
            return {
                "healthy": False,
                "available": False,
                "error": "ChromaDB not installed (install with: pip install chromadb sentence-transformers)"
            }
        
        client = await get_chroma_client()
        
        if not client.is_connected():
            await client.connect()
        
        # Get basic stats
        stats = await client.get_collection_stats()
        
        return {
            "healthy": client.is_connected(),
            "available": True,
            "connected": client.is_connected(),
            "collection_name": client.collection_name,
            "db_path": str(client.db_path),
            "document_count": stats.get("total_documents", 0),
            "chromadb_version": stats.get("chromadb_version", "unknown"),
            "stats": stats
        }
        
    except Exception as e:
        logger.warning(f"ChromaDB health check failed: {str(e)}")
        return {
            "healthy": False,
            "available": CHROMADB_AVAILABLE,
            "connected": False,
            "error": str(e)
        }
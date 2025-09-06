import hashlib
import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger
import uuid

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
        self._connection_lock = asyncio.Lock()
    
    async def connect(self):
        """Initialize ChromaDB connection with improved error handling"""
        if not CHROMADB_AVAILABLE:
            logger.debug("ChromaDB not available - install with: pip install chromadb sentence-transformers")
            return False
        
        async with self._connection_lock:
            if self._connected:
                return True
        
        try:
            # Ensure database directory exists
            self.db_path.mkdir(parents=True, exist_ok=True)
            
            # Clean corrupted data with better error handling
            await self._cleanup_corrupted_data()
            
            # Initialize ChromaDB client with multiple fallback strategies
            client_created = await self._initialize_client()
            if not client_created:
                return False
            
            # Get or create collection with better error handling
            collection_created = await self._initialize_collection()
            if not collection_created:
                return False
            
            self._connected = True
            logger.info("ChromaDB connection established successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {str(e)}")
            await self._log_troubleshooting_info()
            self._client = None
            self._collection = None
            self._connected = False
            return False
    
    async def _cleanup_corrupted_data(self):
        """Clean up corrupted ChromaDB data"""
        try:
            chroma_files = list(self.db_path.glob("*"))
            if chroma_files and any("chroma.sqlite3" in str(f) for f in chroma_files):
                logger.info("Found existing ChromaDB files, checking integrity...")
                
                # Try to identify and remove obviously corrupted files
                corrupted_files = []
                for file in self.db_path.glob("chroma.sqlite3*"):
                    try:
                        # Basic file integrity check
                        if file.stat().st_size == 0:
                            corrupted_files.append(file)
                    except Exception as e:
                        logger.debug(f"Could not check file {file}: {e}")
                        corrupted_files.append(file)
                
                # Remove corrupted files
                for file in corrupted_files:
                    try:
                        file.unlink()
                        logger.info(f"Removed corrupted file: {file}")
                    except Exception as e:
                        logger.warning(f"Could not remove corrupted file {file}: {e}")
                        
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
    
    async def _initialize_client(self):
        """Initialize ChromaDB client with multiple strategies"""
        initialization_strategies = [
            self._init_persistent_client,
            self._init_legacy_client,
            self._init_ephemeral_client
        ]
        
        for i, strategy in enumerate(initialization_strategies):
            try:
                logger.debug(f"Trying client initialization strategy {i+1}/{len(initialization_strategies)}")
                client = await strategy()
                if client:
                    self._client = client
                    logger.info(f"ChromaDB client initialized with strategy {i+1}")
                    return True
            except Exception as e:
                logger.debug(f"Strategy {i+1} failed: {e}")
                continue
        
        logger.error("All client initialization strategies failed")
        return False
    
    async def _init_persistent_client(self):
        """Try new persistent client method"""
        try:
            return chromadb.PersistentClient(path=str(self.db_path))
        except Exception as e:
            logger.debug(f"PersistentClient failed: {e}")
            raise
    
    async def _init_legacy_client(self):
        """Try legacy client configuration"""
        try:
            chroma_settings = ChromaSettings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.db_path),
                anonymized_telemetry=False
            )
            return chromadb.Client(chroma_settings)
        except Exception as e:
            logger.debug(f"Legacy client failed: {e}")
            raise
    
    async def _init_ephemeral_client(self):
        """Fallback to ephemeral (in-memory) client"""
        try:
            logger.warning("Using ephemeral ChromaDB client - data will not persist")
            return chromadb.EphemeralClient()
        except Exception as e:
            logger.debug(f"Ephemeral client failed: {e}")
            raise
    
    async def _initialize_collection(self):
        """Initialize collection with better error handling"""
        if not self._client:
            return False
        
        # Generate unique collection name if there are conflicts
        original_name = self.collection_name
        attempts = 0
        max_attempts = 3
        
        while attempts < max_attempts:
            try:
                current_name = f"{original_name}_{attempts}" if attempts > 0 else original_name
                
                # Try to get existing collection first
                try:
                    self._collection = self._client.get_collection(name=current_name)
                    logger.info(f"Using existing collection: {current_name}")
                    self.collection_name = current_name
                    return True
                except Exception:
                    # Collection doesn't exist, try to create it
                    pass
                
                # Try to create new collection
                self._collection = self._client.create_collection(
                    name=current_name,
                    metadata={
                        "description": "Solana token knowledge base",
                        "created_at": datetime.utcnow().isoformat(),
                        "version": "1.0"
                    }
                )
                logger.info(f"Created new collection: {current_name}")
                self.collection_name = current_name
                return True
                
            except Exception as e:
                logger.debug(f"Collection attempt {attempts + 1} failed: {e}")
                attempts += 1
                
                if attempts < max_attempts:
                    # Try to delete potentially corrupted collection
                    try:
                        self._client.delete_collection(name=current_name)
                        logger.debug(f"Deleted potentially corrupted collection: {current_name}")
                    except Exception:
                        pass
        
        logger.error("All collection initialization attempts failed")
        return False
    
    def is_connected(self) -> bool:
        """Check if ChromaDB is connected"""
        return (
            self._connected and 
            CHROMADB_AVAILABLE and 
            self._client is not None and 
            self._collection is not None
        )
    
    async def disconnect(self):
        """Close ChromaDB connection"""
        async with self._connection_lock:
            if self._client:
                try:
                    # Try to persist data if method exists
                    if hasattr(self._client, 'persist'):
                        self._client.persist()
                        logger.debug("ChromaDB data persisted")
                except Exception as e:
                    logger.warning(f"Error persisting ChromaDB data: {str(e)}")
            
            self._client = None
            self._collection = None
            self._connected = False
            logger.debug("ChromaDB connection closed")
    
    def _generate_id(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Generate unique ID for document"""
        # Use content hash + timestamp + random component for uniqueness
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        timestamp = str(int(datetime.utcnow().timestamp()))
        random_part = uuid.uuid4().hex[:6]
        return f"{content_hash}_{timestamp}_{random_part}"
    
    async def add_document(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """Add document to knowledge base with better error handling"""
        if not self.is_connected():
            success = await self.connect()
            if not success:
                raise Exception("ChromaDB not available")
        
        try:
            if doc_id is None:
                doc_id = self._generate_id(content, metadata)
            
            # Ensure doc_id is unique by checking if it already exists
            max_attempts = 3
            for attempt in range(max_attempts):
                current_doc_id = f"{doc_id}_{attempt}" if attempt > 0 else doc_id
                
                try:
                    # Check if document already exists
                    existing = self._collection.get(ids=[current_doc_id])
                    if existing['ids']:
                        if attempt == max_attempts - 1:
                            # Use the existing document ID with timestamp
                            current_doc_id = f"{doc_id}_{int(datetime.utcnow().timestamp())}"
                        else:
                            continue
                except Exception:
                    # Document doesn't exist, we can use this ID
                    pass
                
                # Prepare metadata
                doc_metadata = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "content_type": "text",
                    "doc_id": current_doc_id,
                    **(metadata or {})
                }
                
                # Add to collection
                self._collection.add(
                    documents=[content],
                    metadatas=[doc_metadata],
                    ids=[current_doc_id]
                )
                
                logger.debug(f"Added document to ChromaDB: {current_doc_id}")
                return current_doc_id
                
        except Exception as e:
            logger.error(f"Error adding document to ChromaDB: {str(e)}")
            raise
    
    def _build_where_clause(self, filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Build proper ChromaDB where clause with explicit operators
        """
        if not filters:
            return None
        
        # If there's only one filter, use simple $eq format
        if len(filters) == 1:
            key, value = list(filters.items())[0]
            return {key: {"$eq": value}}
        
        # Multiple filters need to be combined with $and
        conditions = []
        for key, value in filters.items():
            conditions.append({key: {"$eq": value}})
        
        return {"$and": conditions}

    async def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
        """Search documents in knowledge base with proper where clause handling"""
        if not self.is_connected():
            success = await self.connect()
            if not success:
                raise Exception("ChromaDB not available")
        
        try:
            # Validate parameters
            n_results = max(1, min(n_results, 100))  # Clamp between 1 and 100
            
            # Build proper where clause
            where_clause = self._build_where_clause(where)
            
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Ensure results have expected structure
            if not results.get('documents'):
                results['documents'] = [[]]
            if not results.get('metadatas'):
                results['metadatas'] = [[]]
            if not results.get('distances'):
                results['distances'] = [[]]
            
            logger.debug(f"ChromaDB search returned {len(results['documents'][0])} results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching ChromaDB: {str(e)}")
            # Return empty results structure on error
            return {
                'documents': [[]],
                'metadatas': [[]],
                'distances': [[]]
            }
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        if not self.is_connected():
            success = await self.connect()
            if not success:
                return {"error": "ChromaDB not available", "total_documents": 0}
        
        try:
            # Get collection count
            count = self._collection.count()
            
            stats = {
                "total_documents": count,
                "collection_name": self.collection_name,
                "db_path": str(self.db_path),
                "chromadb_version": getattr(chromadb, '__version__', "unknown"),
                "connected": self._connected,
                "client_type": type(self._client).__name__ if self._client else None
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "error": str(e),
                "total_documents": 0,
                "collection_name": self.collection_name,
                "connected": False
            }
    
    async def _log_troubleshooting_info(self):
        """Log troubleshooting information"""
        logger.info("ChromaDB troubleshooting suggestions:")
        logger.info("  1. Clear database: rm -rf ./shared_data/chroma")
        logger.info("  2. Reinstall ChromaDB: pip uninstall chromadb && pip install chromadb==0.4.24")
        logger.info("  3. Check permissions on ./shared_data/chroma directory")
        logger.info("  4. Try running with --skip-chromadb flag")


# Global ChromaDB client instance
chroma_client = ChromaClient()


async def init_chroma():
    """Initialize ChromaDB connection"""
    if CHROMADB_AVAILABLE:
        success = await chroma_client.connect()
        if success:
            logger.info("ChromaDB initialized successfully")
        else:
            logger.warning("ChromaDB initialization failed - continuing without vector storage")
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
    """Check ChromaDB health with improved error handling"""
    try:
        if not CHROMADB_AVAILABLE:
            return {
                "healthy": False,
                "available": False,
                "error": "ChromaDB not installed (install with: pip install chromadb sentence-transformers)"
            }
        
        client = await get_chroma_client()
        
        # Try to connect if not already connected
        if not client.is_connected():
            connection_success = await client.connect()
            if not connection_success:
                return {
                    "healthy": False,
                    "available": True,
                    "connected": False,
                    "error": "ChromaDB available but connection failed",
                    "recommendation": "Try clearing database: rm -rf ./shared_data/chroma"
                }
        
        # Get basic stats to verify functionality
        stats = await client.get_collection_stats()
        
        # Check if stats indicate an error
        if "error" in stats:
            return {
                "healthy": False,
                "available": True,
                "connected": client.is_connected(),
                "error": f"ChromaDB functional error: {stats['error']}",
                "stats": stats
            }
        
        return {
            "healthy": client.is_connected(),
            "available": True,
            "connected": client.is_connected(),
            "collection_name": client.collection_name,
            "db_path": str(client.db_path),
            "document_count": stats.get("total_documents", 0),
            "chromadb_version": stats.get("chromadb_version", "unknown"),
            "client_type": stats.get("client_type", "unknown"),
            "stats": stats
        }
        
    except Exception as e:
        logger.warning(f"ChromaDB health check failed: {str(e)}")
        return {
            "healthy": False,
            "available": CHROMADB_AVAILABLE,
            "connected": False,
            "error": str(e),
            "recommendation": "Check ChromaDB installation and configuration"
        }
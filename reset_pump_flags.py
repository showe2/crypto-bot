#!/usr/bin/env python3
"""
Script to reset all pump analysis flags from true back to false
This allows tokens to be re-analyzed by the pump detection system
"""

import asyncio
import json
import time
from pathlib import Path
import sys

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.utils.chroma_client import get_chroma_client
from loguru import logger

async def reset_pump_flags():
    """Reset all pump analysis flags from true to false"""
    try:
        # Connect to ChromaDB
        chroma_client = await get_chroma_client()
        if not chroma_client.is_connected():
            logger.error("❌ ChromaDB not available")
            return False
        
        logger.info("🔍 Searching for tokens with pump:true...")
        
        # Search for all token analyses
        results = await chroma_client.search(
            query="token analysis",
            n_results=1000,  # Get many results
        )
        
        if not results or not results.get("documents") or not results["documents"][0]:
            logger.warning("No token analyses found")
            return True
        
        tokens_updated = 0
        tokens_processed = 0
        
        logger.info(f"📊 Found {len(results['documents'][0])} total documents")
        
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
            
            # Skip if not a token analysis
            if metadata.get("doc_type") != "token_analysis":
                continue
            
            tokens_processed += 1
            token_address = metadata.get("token_address", "unknown")
            
            # Check profiles
            profiles_json = metadata.get("profiles", "{}")
            try:
                profiles = json.loads(profiles_json)
                pump_analyzed = profiles.get("pump", False)
                
                # If pump is true, reset it to false
                if pump_analyzed:
                    logger.info(f"🔄 Resetting pump flag for {metadata.get('token_symbol', 'Unknown')} ({token_address[:8]}...)")
                    
                    # Update profiles
                    profiles["pump"] = False
                    metadata["profiles"] = json.dumps(profiles)
                    metadata["pump_analyzed"] = False
                    metadata["reset_timestamp"] = int(time.time())
                    
                    # Get document info
                    doc_id = metadata.get("doc_id") or f"reset_{int(time.time())}_{token_address[:8]}"
                    
                    # Delete old document
                    try:
                        chroma_client._collection.delete(ids=[doc_id])
                    except Exception as e:
                        logger.debug(f"Could not delete old document {doc_id}: {e}")
                    
                    # Add updated document
                    await chroma_client.add_document(
                        content=doc,
                        metadata=metadata,
                        doc_id=doc_id
                    )
                    
                    tokens_updated += 1
                    
                else:
                    logger.debug(f"✅ {metadata.get('token_symbol', 'Unknown')} already has pump:false")
                    
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"⚠️ Could not parse profiles for {token_address}: {e}")
                continue
        
        logger.info(f"✅ Reset complete:")
        logger.info(f"   📊 Processed: {tokens_processed} token analyses")
        logger.info(f"   🔄 Updated: {tokens_updated} pump flags")
        logger.info(f"   ✅ Available for pump analysis: {tokens_updated}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error resetting pump flags: {e}")
        return False

async def verify_reset():
    """Verify that the reset worked"""
    try:
        chroma_client = await get_chroma_client()
        if not chroma_client.is_connected():
            return
        
        logger.info("🔍 Verifying reset...")
        
        # Search for all token analyses
        results = await chroma_client.search(
            query="token analysis",
            n_results=1000,
        )
        
        if not results or not results.get("documents") or not results["documents"][0]:
            return
        
        pump_true_count = 0
        pump_false_count = 0
        
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
            
            if metadata.get("doc_type") != "token_analysis":
                continue
            
            profiles_json = metadata.get("profiles", "{}")
            try:
                profiles = json.loads(profiles_json)
                if profiles.get("pump", False):
                    pump_true_count += 1
                else:
                    pump_false_count += 1
            except:
                continue
        
        logger.info(f"📊 Verification results:")
        logger.info(f"   🔴 pump:true = {pump_true_count}")
        logger.info(f"   🟢 pump:false = {pump_false_count}")
        
        if pump_true_count == 0:
            logger.info("✅ All pump flags successfully reset!")
        else:
            logger.warning(f"⚠️ {pump_true_count} tokens still have pump:true")
            
    except Exception as e:
        logger.error(f"Error verifying reset: {e}")

async def main():
    """Main function"""
    logger.info("🚀 Starting pump flag reset script...")
    
    # Reset the flags
    success = await reset_pump_flags()
    
    if success:
        # Verify the reset
        await verify_reset()
        logger.info("🎉 Pump flag reset complete!")
    else:
        logger.error("❌ Pump flag reset failed!")
        sys.exit(1)

if __name__ == "__main__":
    # Run the script
    asyncio.run(main())
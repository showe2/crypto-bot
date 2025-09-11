import asyncio
import time
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.services.snapshots.token_snapshot import run_scheduled_snapshots

settings = get_settings()


class SnapshotScheduler:
    """Simple scheduler for running snapshots at regular intervals"""
    
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.interval_seconds = settings.SNAPSHOT_INTERVAL_SECONDS
        self.enabled = settings.SNAPSHOT_ENABLED
        self.stats = {
            "runs_completed": 0,
            "runs_failed": 0,
            "last_run_time": None,
            "next_run_time": None,
            "total_tokens_processed": 0,
            "total_snapshots_successful": 0,
            "total_snapshots_failed": 0
        }
        
    async def start(self):
        """Start the snapshot scheduler"""
        if not self.enabled:
            logger.info("📸 Snapshot scheduler is DISABLED in configuration")
            return False
            
        if self.running:
            return True
            
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        
        logger.info(f"📸 Snapshot scheduler started - running every {self.interval_seconds}s ({self.interval_seconds/3600:.1f}h)")
        return True
    
    async def stop(self):
        """Stop the snapshot scheduler"""
        if not self.running:
            return
            
        self.running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
            
        logger.info("📸 Snapshot scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info(f"📸 Snapshot scheduler loop started (interval: {self.interval_seconds}s)")
        
        while self.running:
            try:
                # Wait for the interval
                await asyncio.sleep(self.interval_seconds)
                
                if not self.running:
                    break
                    
                # Run snapshots
                await self._run_snapshots()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Snapshot scheduler error: {str(e)}")
                # Continue running even after errors
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _run_snapshots(self):
        """Execute snapshot run"""
        try:
            logger.info("🔄 Starting scheduled snapshot run")
            
            # Run the snapshots
            result = await run_scheduled_snapshots()
            
            # Log results
            if result.get("status") == "completed":
                logger.info(
                    f"✅ Scheduled snapshot run completed: "
                    f"{result.get('successful', 0)} successful, {result.get('failed', 0)} failed"
                )
            elif result.get("status") == "no_tokens":
                logger.warning(f"⚠️ Scheduled snapshot run failed: No tokens found")
            else:
                logger.error(f"❌ Scheduled snapshot run failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"❌ Snapshot run exception: {str(e)}")


# Global scheduler instance
snapshot_scheduler = SnapshotScheduler()


# Simple functions
async def start_snapshot_scheduler():
    """Start the snapshot scheduler"""
    return await snapshot_scheduler.start()


async def stop_snapshot_scheduler():
    """Stop the snapshot scheduler"""
    await snapshot_scheduler.stop()
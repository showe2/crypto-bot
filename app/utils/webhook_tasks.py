import asyncio
import time
from typing import Dict, Any, Optional
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class WebhookTaskQueue:
    """Simple async task queue for webhook event processing"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.workers = []
        self.running = False
        self.stats = {
            "total_processed": 0,
            "total_failed": 0,
            "queue_size": 0
        }
    
    async def start_workers(self, num_workers: int = 2):
        """Start background workers"""
        if self.running:
            return
        
        self.running = True
        logger.info(f"Starting {num_workers} webhook workers")
        
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
    
    async def stop_workers(self):
        """Stop background workers"""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping webhook workers")
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
    
    async def add_task(self, event_type: str, payload: Dict[str, Any], priority: str = "normal"):
        """Add a webhook event to the processing queue"""
        task = {
            "event_type": event_type,
            "payload": payload,
            "priority": priority,
            "timestamp": time.time(),
            "retries": 0
        }
        
        await self.queue.put(task)
        self.stats["queue_size"] = self.queue.qsize()
        
        logger.debug(f"Added {event_type} task to queue (queue size: {self.queue.qsize()})")
    
    async def _worker(self, worker_name: str):
        """Background worker to process webhook events"""
        logger.info(f"Webhook worker {worker_name} started")
        
        while self.running:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                # Process the task
                await self._process_task(task, worker_name)
                
                # Mark task as done
                self.queue.task_done()
                self.stats["queue_size"] = self.queue.qsize()
                
            except asyncio.TimeoutError:
                # No tasks in queue, continue
                continue
            except asyncio.CancelledError:
                # Worker was cancelled
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {str(e)}")
                self.stats["total_failed"] += 1
        
        logger.info(f"Webhook worker {worker_name} stopped")
    
    async def _process_task(self, task: Dict[str, Any], worker_name: str):
        """Process a single webhook task"""
        start_time = time.time()
        event_type = task["event_type"]
        payload = task["payload"]
        
        try:
            logger.debug(f"Worker {worker_name} processing {event_type} event")
            
            # Process based on event type
            if event_type == "mint":
                await self._process_mint_background(payload)
            elif event_type == "pool":
                await self._process_pool_background(payload)
            elif event_type == "transaction":
                await self._process_transaction_background(payload)
            else:
                logger.warning(f"Unknown event type: {event_type}")
            
            processing_time = time.time() - start_time
            self.stats["total_processed"] += 1
            
            logger.info(
                f"Background task completed: {event_type} ({processing_time:.2f}s)",
                extra={
                    "webhook_background": True,
                    "event_type": event_type,
                    "processing_time": processing_time,
                    "worker": worker_name
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.stats["total_failed"] += 1
            
            logger.error(
                f"Background task failed: {event_type} - {str(e)}",
                extra={
                    "webhook_background": True,
                    "event_type": event_type,
                    "error": str(e),
                    "processing_time": processing_time,
                    "worker": worker_name
                }
            )
            
            # Retry logic could be added here
            if task["retries"] < 3:
                task["retries"] += 1
                await self.queue.put(task)
                logger.info(f"Retrying {event_type} task (attempt {task['retries']})")
    
    async def _process_mint_background(self, payload: Dict[str, Any]):
        """Background processing for mint events"""
        mint_address = payload.get("mint")
        if not mint_address:
            return
        
        # Example background tasks:
        # 1. Store event in database
        # 2. Trigger token analysis
        # 3. Send notifications
        
        logger.info(f"Background processing mint: {mint_address}")
        
        # Simulate some processing
        await asyncio.sleep(0.1)
        
        # Here you could:
        # - Save to database
        # - Trigger token analysis via API manager
        # - Send Discord/Telegram notifications
        # - Update cache with new token info
        
    async def _process_pool_background(self, payload: Dict[str, Any]):
        """Background processing for pool events"""
        pool_address = payload.get("pool")
        if not pool_address:
            return
        
        logger.info(f"Background processing pool: {pool_address}")
        
        # Simulate processing
        await asyncio.sleep(0.1)
        
        # Example tasks:
        # - Analyze new trading pair
        # - Update liquidity tracking
        # - Alert for interesting pairs
        
    async def _process_transaction_background(self, payload: Dict[str, Any]):
        """Background processing for transaction events"""
        signature = payload.get("signature")
        if not signature:
            return
        
        logger.info(f"Background processing transaction: {signature}")
        
        # Simulate processing
        await asyncio.sleep(0.1)
        
        # Example tasks:
        # - Analyze whale movements
        # - Track suspicious activities
        # - Update transaction metrics
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            "running": self.running,
            "workers_count": len(self.workers),
            "queue_size": self.queue.qsize(),
            "total_processed": self.stats["total_processed"],
            "total_failed": self.stats["total_failed"],
            "success_rate": (
                self.stats["total_processed"] / 
                (self.stats["total_processed"] + self.stats["total_failed"]) * 100
                if (self.stats["total_processed"] + self.stats["total_failed"]) > 0 else 0
            )
        }


# Global task queue instance
webhook_task_queue = WebhookTaskQueue()


# Convenience functions
async def queue_webhook_task(event_type: str, payload: Dict[str, Any], priority: str = "normal"):
    """Queue a webhook event for background processing"""
    await webhook_task_queue.add_task(event_type, payload, priority)


async def start_webhook_workers():
    """Start webhook background workers"""
    await webhook_task_queue.start_workers()


async def stop_webhook_workers():
    """Stop webhook background workers"""
    await webhook_task_queue.stop_workers()


async def get_webhook_queue_stats() -> Dict[str, Any]:
    """Get webhook queue statistics"""
    return webhook_task_queue.get_stats()
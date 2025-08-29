import asyncio
import time
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime

class WebhookTaskQueue:
    """Async task queue for webhook event processing with AI-enhanced deep analysis"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.workers = []
        self.running = False
        self.stats = {
            "total_processed": 0,
            "total_failed": 0,
            "queue_size": 0,
            "deep_analyses_triggered": 0,
            "ai_analyses_completed": 0
        }
    
    async def start_workers(self, num_workers: int = 3):  # Increased workers for deep analysis
        """Start background workers for deep analysis processing"""
        if self.running:
            return
        
        self.running = True
        logger.info(f"Starting {num_workers} webhook workers with AI-enhanced deep analysis")
        
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
            "retries": 0,
            "analysis_type": "deep_ai_enhanced"  # Mark all tasks as using deep analysis
        }
        
        await self.queue.put(task)
        self.stats["queue_size"] = self.queue.qsize()
        
        logger.debug(f"Added {event_type} task to queue for AI-enhanced deep analysis (queue size: {self.queue.qsize()})")
    
    async def _worker(self, worker_name: str):
        """Background worker to process webhook events with deep analysis"""
        logger.info(f"Webhook worker {worker_name} started (AI-enhanced deep analysis)")
        
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
        """Process a single webhook task with deep analysis"""
        start_time = time.time()
        event_type = task["event_type"]
        
        try:
            logger.debug(f"Worker {worker_name} processing {event_type} event with AI-enhanced deep analysis")
            
            # Extract token information for analysis triggering
            payload = task["payload"]
            tokens_for_analysis = self._extract_tokens_for_analysis(payload, event_type)
            
            if tokens_for_analysis:
                self.stats["deep_analyses_triggered"] += len(tokens_for_analysis)
                logger.info(f"🤖 Worker {worker_name} triggered deep analysis for {len(tokens_for_analysis)} tokens from {event_type} event")
                
                # Trigger deep analysis for each token
                from app.services.ai.ai_token_analyzer import analyze_token_deep_comprehensive
                from app.services.analysis_storage import analysis_storage  # Add this import
                
                for token_address in tokens_for_analysis:
                    try:
                        logger.info(f"🤖 Starting deep AI analysis for webhook token: {token_address}")
                        
                        analysis_result = await analyze_token_deep_comprehensive(
                            token_address, 
                            f"webhook_{event_type}"
                        )
                        
                        # Store analysis in database
                        if analysis_result:
                            # Add webhook metadata
                            analysis_result["metadata"]["webhook_event_type"] = event_type
                            analysis_result["metadata"]["webhook_timestamp"] = datetime.utcnow().isoformat()
                            analysis_result["metadata"]["source"] = f"webhook_{event_type}"
                            
                            # Store in database
                            try:
                                await analysis_storage.store_analysis(analysis_result)
                                logger.info(f"✅ Analysis stored in DB for webhook token: {token_address}")
                            except Exception as store_error:
                                logger.error(f"❌ Failed to store analysis in DB: {str(store_error)}")
                                raise store_error
                        
                        # Check if AI analysis was completed
                        if analysis_result.get("ai_analysis") and analysis_result.get("metadata", {}).get("ai_analysis_completed"):
                            self.stats["ai_analyses_completed"] += 1
                            logger.info(f"✅ AI-enhanced analysis completed for {token_address}")
                        else:
                            logger.info(f"✅ Traditional analysis completed for {token_address} (AI not available)")
                        
                    except Exception as analysis_error:
                        logger.error(f"❌ Deep analysis failed for {token_address}: {str(analysis_error)}")
                        continue
            
            processing_time = time.time() - start_time
            self.stats["total_processed"] += 1
            
            logger.info(
                f"✅ Background task completed: {event_type} ({processing_time:.2f}s) - {len(tokens_for_analysis)} tokens analyzed",
                extra={
                    "webhook_background": True,
                    "event_type": event_type,
                    "processing_time": processing_time,
                    "worker": worker_name,
                    "analysis_type": "deep_ai_enhanced",
                    "tokens_analyzed": len(tokens_for_analysis),
                    "ai_enhanced": True
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.stats["total_failed"] += 1
            
            logger.error(
                f"❌ Background task failed: {event_type} - {str(e)}",
                extra={
                    "webhook_background": True,
                    "event_type": event_type,
                    "error": str(e),
                    "processing_time": processing_time,
                    "worker": worker_name,
                    "analysis_type": "deep_ai_enhanced"
                }
            )
            
            # Retry logic for failed tasks
            if task["retries"] < 3:
                task["retries"] += 1
                await self.queue.put(task)
                logger.info(f"Retrying {event_type} task (attempt {task['retries']})")
    
    def _extract_tokens_for_analysis(self, payload: Dict[str, Any], event_type: str) -> list:
        """Extract token addresses that should trigger deep analysis - MINT EVENTS ONLY"""
        tokens = []
        
        try:
            # Handle mint events only
            if event_type == "mint":
                # For mint events, extract the minted token
                if payload.get("data"):
                    for data_item in payload["data"]:
                        if data_item.get("accountData"):
                            for account_data in data_item["accountData"]:
                                if account_data.get("mint"):
                                    tokens.append(account_data["mint"])
                        
                        if data_item.get("tokenTransfers"):
                            for transfer in data_item["tokenTransfers"]:
                                if transfer.get("mint") and transfer.get("fromTokenAccount") == "":
                                    tokens.append(transfer["mint"])
            
            # Remove duplicates and return the first token for mint events
            tokens = list(set(tokens))
            
            if event_type == "mint":
                return tokens[:1]  # Only analyze the main minted token
            
        except Exception as e:
            logger.warning(f"Error extracting tokens from {event_type} payload: {str(e)}")
            
        return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics with AI analysis metrics"""
        total_events = self.stats["total_processed"] + self.stats["total_failed"]
        success_rate = (
            self.stats["total_processed"] / total_events * 100
            if total_events > 0 else 0
        )
        
        ai_completion_rate = (
            self.stats["ai_analyses_completed"] / max(1, self.stats["deep_analyses_triggered"]) * 100
        )
        
        return {
            "running": self.running,
            "workers_count": len(self.workers),
            "queue_size": self.queue.qsize(),
            "total_processed": self.stats["total_processed"],
            "total_failed": self.stats["total_failed"],
            "success_rate": round(success_rate, 2),
            "analysis_type": "deep_ai_enhanced",
            "deep_analyses_triggered": self.stats["deep_analyses_triggered"],
            "ai_analyses_completed": self.stats["ai_analyses_completed"],
            "ai_completion_rate": round(ai_completion_rate, 2),
            "ai_enhanced": True
        }


# Global task queue instance
webhook_task_queue = WebhookTaskQueue()


# Convenience functions for easy integration
async def queue_webhook_task(event_type: str, payload: Dict[str, Any], priority: str = "normal"):
    """Queue a webhook event for background processing with deep analysis"""
    await webhook_task_queue.add_task(event_type, payload, priority)


async def start_webhook_workers(num_workers: int = 3):  # Increased default workers
    """Start webhook background workers with AI-enhanced deep analysis"""
    await webhook_task_queue.start_workers(num_workers)


async def stop_webhook_workers():
    """Stop webhook background workers"""
    await webhook_task_queue.stop_workers()


async def get_webhook_queue_stats() -> Dict[str, Any]:
    """Get webhook queue statistics with AI metrics"""
    return webhook_task_queue.get_stats()


def is_webhook_system_running() -> bool:
    """Check if webhook system is running"""
    return webhook_task_queue.running


async def ensure_webhook_workers_running():
    """Ensure webhook workers are running (auto-start if needed)"""
    if not webhook_task_queue.running:
        logger.info("Webhook workers not running, starting them now with AI-enhanced deep analysis...")
        await start_webhook_workers()
    return webhook_task_queue.running
import asyncio
import time
import hashlib
from typing import Dict, Any, Optional, Set
from loguru import logger
from datetime import datetime

class WebhookTaskQueue:
    """Async task queue for webhook event processing with deduplication"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.workers = []
        self.running = False
        self.stats = {
            "total_processed": 0,
            "total_failed": 0,
            "queue_size": 0,
            "security_analyses_triggered": 0,
            "security_analyses_passed": 0,
            "security_analyses_failed": 0,
            "duplicates_prevented": 0
        }
        # Deduplication cache: token_address -> last_processed_timestamp
        self._processed_tokens: Dict[str, float] = {}
        self._dedup_window = 300  # 5 minutes deduplication window
    
    def _generate_task_hash(self, token_address: str, event_type: str) -> str:
        """Generate unique hash for task deduplication"""
        # Round timestamp to nearest 5 minutes for deduplication window
        current_time = time.time()
        time_bucket = int(current_time // self._dedup_window) * self._dedup_window
        
        hash_input = f"{token_address}_{event_type}_{time_bucket}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]
    
    def _is_duplicate_task(self, token_address: str, event_type: str) -> bool:
        """Check if this is a duplicate task within the deduplication window"""
        if not token_address:
            return False
        
        task_hash = self._generate_task_hash(token_address, event_type)
        current_time = time.time()
        
        # Clean old entries
        expired_keys = [
            token for token, timestamp in self._processed_tokens.items()
            if current_time - timestamp > self._dedup_window
        ]
        for key in expired_keys:
            del self._processed_tokens[key]
        
        # Check if task was recently processed
        if task_hash in self._processed_tokens:
            time_since_last = current_time - self._processed_tokens[task_hash]
            logger.info(f"Duplicate task detected for {token_address} ({time_since_last:.1f}s ago) - skipping")
            self.stats["duplicates_prevented"] += 1
            return True
        
        # Mark as processed
        self._processed_tokens[task_hash] = current_time
        return False
    
    async def start_workers(self, num_workers: int = 3):
        """Start background workers"""
        if self.running:
            return
        
        self.running = True
        logger.info(f"Starting {num_workers} webhook workers with security-only analysis")
        
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
        """Add a webhook event to the processing queue with deduplication"""
        # Extract token address for deduplication check
        token_address = None
        try:
            token_address = self._extract_primary_token(payload, event_type)
        except Exception as e:
            logger.debug(f"Could not extract token for deduplication: {e}")
        
        # Check for duplicates
        if token_address and self._is_duplicate_task(token_address, event_type):
            logger.info(f"Prevented duplicate {event_type} task for {token_address}")
            return
        
        task = {
            "event_type": event_type,
            "payload": payload,
            "priority": priority,
            "timestamp": time.time(),
            "retries": 0,
            "analysis_type": "security_only",
            "primary_token": token_address  # Store for processing
        }
        
        await self.queue.put(task)
        self.stats["queue_size"] = self.queue.qsize()
        
        logger.debug(f"Added {event_type} task to queue (token: {token_address}, queue size: {self.queue.qsize()})")
    
    def _extract_primary_token(self, payload: Dict[str, Any], event_type: str) -> Optional[str]:
        """Extract the primary token from payload for deduplication"""
        try:
            if event_type == "mint" and payload.get("data"):
                for data_item in payload["data"]:
                    if data_item.get("accountData"):
                        for account_data in data_item["accountData"]:
                            if account_data.get("mint"):
                                return account_data["mint"]
                    
                    if data_item.get("tokenTransfers"):
                        for transfer in data_item["tokenTransfers"]:
                            if transfer.get("mint") and transfer.get("fromTokenAccount") == "":
                                return transfer["mint"]
        except Exception:
            pass
        return None
    
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
        """Process a single webhook task - security analysis only"""
        start_time = time.time()
        event_type = task["event_type"]
        
        try:
            logger.debug(f"Worker {worker_name} processing {event_type} event")
            
            # Extract token information for analysis
            payload = task["payload"]
            tokens_for_analysis = self._extract_tokens_for_analysis(payload, event_type)
            
            if tokens_for_analysis:
                self.stats["security_analyses_triggered"] += len(tokens_for_analysis)
                logger.info(f"Worker {worker_name} triggered security analysis for {len(tokens_for_analysis)} tokens from {event_type} event")
                
                # Import security-only analysis function
                from app.services.token_analyzer import analyze_token_security_only
                
                for token_address in tokens_for_analysis:
                    try:
                        logger.info(f"Starting security-only analysis for webhook token: {token_address}")
                        
                        analysis_result = await analyze_token_security_only(
                            token_address, 
                            f"webhook_{event_type}"
                        )
                        
                        # Add webhook metadata to the analysis result
                        if analysis_result and "metadata" not in analysis_result:
                            analysis_result["metadata"] = {}
                        
                        if analysis_result:
                            analysis_result["metadata"].update({
                                "webhook_event_type": event_type,
                                "webhook_timestamp": datetime.utcnow().isoformat(),
                                "source": f"webhook_{event_type}",
                                "worker_name": worker_name
                            })
                        
                        # Check if security analysis passed and was stored
                        if analysis_result:
                            security_passed = analysis_result.get("metadata", {}).get("security_check_passed", False)
                            stored_in_db = analysis_result.get("stored_in_db", False)
                            
                            if security_passed and stored_in_db:
                                self.stats["security_analyses_passed"] += 1
                                logger.info(f"✅ Security analysis PASSED and stored for {token_address}")
                            elif security_passed:
                                self.stats["security_analyses_passed"] += 1
                                logger.warning(f"⚠️ Security analysis PASSED but storage failed for {token_address}")
                            else:
                                self.stats["security_analyses_failed"] += 1
                                logger.warning(f"❌ Security analysis FAILED for {token_address} - not stored")
                        
                    except Exception as analysis_error:
                        self.stats["security_analyses_failed"] += 1
                        logger.error(f"Security analysis failed for {token_address}: {str(analysis_error)}")
                        continue
            
            processing_time = time.time() - start_time
            self.stats["total_processed"] += 1
            
            logger.info(
                f"Webhook task completed: {event_type} ({processing_time:.2f}s) - {len(tokens_for_analysis)} tokens analyzed"
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.stats["total_failed"] += 1
            
            logger.error(f"Webhook task failed: {event_type} - {str(e)}")
            
            # Retry logic for failed tasks
            if task["retries"] < 2:
                task["retries"] += 1
                await self.queue.put(task)
                logger.info(f"Retrying {event_type} task (attempt {task['retries']})")
    
    def _extract_tokens_for_analysis(self, payload: Dict[str, Any], event_type: str) -> list:
        """Extract token addresses for analysis - MINT EVENTS ONLY"""
        tokens = []
        
        try:
            # Handle mint events only
            if event_type == "mint":
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
            
            # Remove duplicates and return first token only
            tokens = list(set(tokens))
            
            if event_type == "mint":
                return tokens[:1]  # Only analyze the main minted token
            
        except Exception as e:
            logger.warning(f"Error extracting tokens from {event_type} payload: {str(e)}")
            
        return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics with security analysis metrics"""
        total_events = self.stats["total_processed"] + self.stats["total_failed"]
        success_rate = (
            self.stats["total_processed"] / total_events * 100
            if total_events > 0 else 0
        )
        
        total_security_analyses = self.stats["security_analyses_passed"] + self.stats["security_analyses_failed"]
        security_pass_rate = (
            self.stats["security_analyses_passed"] / max(1, total_security_analyses) * 100
        )
        
        return {
            "running": self.running,
            "workers_count": len(self.workers),
            "queue_size": self.queue.qsize(),
            "total_processed": self.stats["total_processed"],
            "total_failed": self.stats["total_failed"],
            "success_rate": round(success_rate, 2),
            "analysis_type": "security_only",
            "security_analyses_triggered": self.stats["security_analyses_triggered"],
            "security_analyses_passed": self.stats["security_analyses_passed"],
            "security_analyses_failed": self.stats["security_analyses_failed"],
            "security_pass_rate": round(security_pass_rate, 2),
            "duplicates_prevented": self.stats["duplicates_prevented"],
            "deduplication_enabled": True,
            "dedup_window_seconds": self._dedup_window
        }


# Global task queue instance
webhook_task_queue = WebhookTaskQueue()


# Convenience functions
async def queue_webhook_task(event_type: str, payload: Dict[str, Any], priority: str = "normal"):
    """Queue a webhook event for background processing with deduplication"""
    await webhook_task_queue.add_task(event_type, payload, priority)


async def start_webhook_workers(num_workers: int = 3):
    """Start webhook background workers"""
    await webhook_task_queue.start_workers(num_workers)


async def stop_webhook_workers():
    """Stop webhook background workers"""
    await webhook_task_queue.stop_workers()


async def get_webhook_queue_stats() -> Dict[str, Any]:
    """Get webhook queue statistics"""
    return webhook_task_queue.get_stats()


def is_webhook_system_running() -> bool:
    """Check if webhook system is running"""
    return webhook_task_queue.running


async def ensure_webhook_workers_running():
    """Ensure webhook workers are running"""
    if not webhook_task_queue.running:
        logger.info("Webhook workers not running, starting them...")
        await start_webhook_workers()
    return webhook_task_queue.running
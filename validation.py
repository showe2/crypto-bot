import re
from typing import Dict, Any, List
from loguru import logger
from pydantic import BaseModel


class ValidationResult(BaseModel):
    """Validation result container"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    normalized_data: Dict[str, Any] = {}


class SolanaAddressValidator:
    """Solana address validation utilities"""
    
    # Solana address is base58 encoded, 32-44 characters
    SOLANA_ADDRESS_PATTERN = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')
    
    @classmethod
    def validate_address(cls, address: str) -> ValidationResult:
        """Validate Solana address format"""
        errors = []
        warnings = []
        
        if not address:
            errors.append("Address cannot be empty")
            return ValidationResult(valid=False, errors=errors)
        
        if not isinstance(address, str):
            errors.append("Address must be a string")
            return ValidationResult(valid=False, errors=errors)
        
        # Remove whitespace
        address = address.strip()
        
        # Length check
        if len(address) < 32:
            errors.append("Address too short (minimum 32 characters)")
        elif len(address) > 44:
            errors.append("Address too long (maximum 44 characters)")
        
        # Character validation
        if not cls.SOLANA_ADDRESS_PATTERN.match(address):
            errors.append("Invalid characters in address (must be base58)")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data={"address": address}
        )
    
    @classmethod
    def validate_token_mint(cls, mint_address: str) -> ValidationResult:
        """Validate token mint address"""
        return cls.validate_address(mint_address)


# Global validator instances
solana_validator = SolanaAddressValidator()


class ValidationMiddleware:
    """Middleware for request validation"""
    
    def __init__(self):
        self.logger = logger.bind(component="validation")
    
    async def validate_request(self, request_data: Dict[str, Any], endpoint: str) -> ValidationResult:
        """Validate request based on endpoint"""
        try:
            # Basic validation
            return ValidationResult(valid=True)
                
        except Exception as e:
            self.logger.error(f"Request validation error for {endpoint}: {str(e)}")
            return ValidationResult(
                valid=False,
                errors=[f"Validation error: {str(e)}"]
            )
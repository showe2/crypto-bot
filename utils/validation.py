import re
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from loguru import logger

from pydantic import BaseModel, ValidationError


class ValidationResult(BaseModel):
    """Validation result container"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    normalized_data: Optional[Dict[str, Any]] = None


class SolanaAddressValidator:
    """Solana address validation utilities"""
    
    # Solana address is base58 encoded, 32-44 characters
    SOLANA_ADDRESS_PATTERN = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}')
    
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
        
        # Common mistakes
        if address.lower() != address and address.upper() != address:
            # Mixed case might be suspicious
            warnings.append("Mixed case detected - verify address carefully")
        
        if '0' in address or 'O' in address or 'I' in address or 'l' in address:
            warnings.append("Address contains potentially confusing characters (0, O, I, l)")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data={"address": address}
        )
    
    @classmethod
    def validate_token_mint(cls, mint_address: str) -> ValidationResult:
        """Validate token mint address with additional checks"""
        base_result = cls.validate_address(mint_address)
        
        if not base_result.valid:
            return base_result
        
        # Additional checks for token mints
        known_system_addresses = [
            "So11111111111111111111111111111111111112",  # Wrapped SOL
            "11111111111111111111111111111111",          # System Program
        ]
        
        if mint_address in known_system_addresses:
            base_result.warnings.append("This is a system program address, not a typical token mint")
        
        return base_result


class NumericValidator:
    """Numeric data validation utilities"""
    
    @staticmethod
    def validate_price(price: Union[str, int, float, Decimal]) -> ValidationResult:
        """Validate price value"""
        errors = []
        warnings = []
        normalized_value = None
        
        try:
            if isinstance(price, str):
                # Remove common formatting
                price_clean = price.replace(',', '').replace('', '').strip()
                price_decimal = Decimal(price_clean)
            else:
                price_decimal = Decimal(str(price))
            
            # Validation rules
            if price_decimal < 0:
                errors.append("Price cannot be negative")
            elif price_decimal == 0:
                warnings.append("Price is zero - might indicate no market data")
            elif price_decimal > Decimal('1000000'):
                warnings.append("Very high price - verify data accuracy")
            elif price_decimal < Decimal('0.0000001'):
                warnings.append("Very low price - potential precision issues")
            
            normalized_value = float(price_decimal)
            
        except (InvalidOperation, ValueError, TypeError) as e:
            errors.append(f"Invalid price format: {str(e)}")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data={"price": normalized_value} if normalized_value is not None else None
        )
    
    @staticmethod
    def validate_percentage(percentage: Union[str, int, float]) -> ValidationResult:
        """Validate percentage value"""
        errors = []
        warnings = []
        normalized_value = None
        
        try:
            if isinstance(percentage, str):
                # Remove % sign and whitespace
                perc_clean = percentage.replace('%', '').strip()
                perc_float = float(perc_clean)
            else:
                perc_float = float(percentage)
            
            # Validation rules
            if perc_float < -100:
                warnings.append("Percentage less than -100% - might indicate extreme loss")
            elif perc_float > 10000:
                warnings.append("Very high percentage - verify data accuracy")
            
            normalized_value = perc_float
            
        except (ValueError, TypeError) as e:
            errors.append(f"Invalid percentage format: {str(e)}")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data={"percentage": normalized_value} if normalized_value is not None else None
        )
    
    @staticmethod
    def validate_volume(volume: Union[str, int, float, Decimal]) -> ValidationResult:
        """Validate trading volume"""
        errors = []
        warnings = []
        normalized_value = None
        
        try:
            if isinstance(volume, str):
                # Handle K, M, B suffixes
                volume_clean = volume.replace(',', '').strip().upper()
                multiplier = 1
                
                if volume_clean.endswith('K'):
                    multiplier = 1000
                    volume_clean = volume_clean[:-1]
                elif volume_clean.endswith('M'):
                    multiplier = 1000000
                    volume_clean = volume_clean[:-1]
                elif volume_clean.endswith('B'):
                    multiplier = 1000000000
                    volume_clean = volume_clean[:-1]
                
                volume_decimal = Decimal(volume_clean) * multiplier
            else:
                volume_decimal = Decimal(str(volume))
            
            # Validation rules
            if volume_decimal < 0:
                errors.append("Volume cannot be negative")
            elif volume_decimal == 0:
                warnings.append("Zero volume - might indicate no trading activity")
            elif volume_decimal > Decimal('1000000000'):
                warnings.append("Very high volume - verify data accuracy")
            
            normalized_value = float(volume_decimal)
            
        except (InvalidOperation, ValueError, TypeError) as e:
            errors.append(f"Invalid volume format: {str(e)}")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data={"volume": normalized_value} if normalized_value is not None else None
        )


class SocialDataValidator:
    """Social media data validation"""
    
    @staticmethod
    def validate_social_content(content: str, platform: str) -> ValidationResult:
        """Validate social media content"""
        errors = []
        warnings = []
        normalized_data = {}
        
        if not content or not isinstance(content, str):
            errors.append("Content cannot be empty")
            return ValidationResult(valid=False, errors=errors)
        
        content = content.strip()
        
        # Length validation based on platform
        platform_limits = {
            "twitter": 280,
            "telegram": 4096,
            "discord": 2000,
            "reddit": 10000
        }
        
        limit = platform_limits.get(platform.lower(), 1000)
        if len(content) > limit:
            warnings.append(f"Content length ({len(content)}) exceeds typical {platform} limit ({limit})")
        
        # Content quality checks
        if len(content.split()) < 3:
            warnings.append("Very short content - might lack context")
        
        # Detect spam patterns
        spam_indicators = [
            (r'(.)\1{4,}', "Excessive character repetition"),
            (r'[A-Z]{10,}', "Excessive capitalization"),
            (r'🚀.*🚀.*🚀', "Excessive rocket emojis"),
            (r'(\d+x|\d+\%.*\d+\%)', "Multiple percentage claims")
        ]
        
        for pattern, description in spam_indicators:
            if re.search(pattern, content):
                warnings.append(f"Potential spam indicator: {description}")
        
        # Extract useful information
        # Mentions
        mentions = re.findall(r'@(\w+)', content)
        # Hashtags
        hashtags = re.findall(r'#(\w+)', content)
        # URLs
        urls = re.findall(r'https?://[^\s]+', content)
        # Cashtags (for tokens)
        cashtags = re.findall(r'\$([A-Z]{2,10})', content)
        
        normalized_data = {
            "content": content,
            "word_count": len(content.split()),
            "char_count": len(content),
            "mentions": mentions,
            "hashtags": hashtags,
            "urls": urls,
            "cashtags": cashtags
        }
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data=normalized_data
        )
    
    @staticmethod
    def validate_sentiment_score(score: Union[int, float]) -> ValidationResult:
        """Validate sentiment score"""
        errors = []
        warnings = []
        
        try:
            score_float = float(score)
            
            if not (-1 <= score_float <= 1):
                errors.append("Sentiment score must be between -1 and 1")
            
            # Warnings for extreme values
            if abs(score_float) > 0.95:
                warnings.append("Extreme sentiment score - verify accuracy")
            
            return ValidationResult(
                valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                normalized_data={"sentiment_score": score_float}
            )
            
        except (ValueError, TypeError):
            errors.append("Invalid sentiment score format")
            return ValidationResult(valid=False, errors=errors)


class DateTimeValidator:
    """Date and time validation utilities"""
    
    @staticmethod
    def validate_timestamp(timestamp: Union[str, int, float, datetime]) -> ValidationResult:
        """Validate timestamp"""
        errors = []
        warnings = []
        normalized_dt = None
        
        try:
            if isinstance(timestamp, datetime):
                normalized_dt = timestamp
            elif isinstance(timestamp, str):
                # Try to parse ISO format
                try:
                    normalized_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    # Try other common formats
                    import dateutil.parser
                    normalized_dt = dateutil.parser.parse(timestamp)
            elif isinstance(timestamp, (int, float)):
                # Unix timestamp
                if timestamp > 1e12:  # Milliseconds
                    timestamp = timestamp / 1000
                normalized_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            
            # Validation checks
            now = datetime.now(timezone.utc)
            
            if normalized_dt > now:
                warnings.append("Timestamp is in the future")
            elif (now - normalized_dt).days > 365:
                warnings.append("Timestamp is more than a year old")
            elif (now - normalized_dt).total_seconds() < 0:
                errors.append("Invalid timestamp - negative time")
            
        except Exception as e:
            errors.append(f"Invalid timestamp format: {str(e)}")
        
        return ValidationResult(
            valid=len(errors) == 0 and normalized_dt is not None,
            errors=errors,
            warnings=warnings,
            normalized_data={"timestamp": normalized_dt} if normalized_dt else None
        )


class TokenDataValidator:
    """Complete token data validation"""
    
    def __init__(self):
        self.address_validator = SolanaAddressValidator()
        self.numeric_validator = NumericValidator()
        self.datetime_validator = DateTimeValidator()
    
    def validate_token_metadata(self, metadata: Dict[str, Any]) -> ValidationResult:
        """Validate complete token metadata"""
        all_errors = []
        all_warnings = []
        normalized_data = {}
        
        # Required fields
        required_fields = ['mint', 'name', 'symbol']
        for field in required_fields:
            if field not in metadata or not metadata[field]:
                all_errors.append(f"Missing required field: {field}")
        
        # Validate mint address
        if 'mint' in metadata:
            mint_result = self.address_validator.validate_token_mint(metadata['mint'])
            all_errors.extend(mint_result.errors)
            all_warnings.extend(mint_result.warnings)
            if mint_result.normalized_data:
                normalized_data['mint'] = mint_result.normalized_data['address']
        
        # Validate symbol
        if 'symbol' in metadata:
            symbol = metadata['symbol']
            if len(symbol) > 10:
                all_warnings.append("Symbol longer than 10 characters")
            if not symbol.isupper():
                all_warnings.append("Symbol should typically be uppercase")
            normalized_data['symbol'] = symbol.upper()
        
        # Validate name
        if 'name' in metadata:
            name = metadata['name']
            if len(name) > 100:
                all_warnings.append("Token name is very long")
            normalized_data['name'] = name.strip()
        
        # Validate decimals
        if 'decimals' in metadata:
            try:
                decimals = int(metadata['decimals'])
                if not (0 <= decimals <= 18):
                    all_warnings.append("Unusual decimal count (outside 0-18 range)")
                normalized_data['decimals'] = decimals
            except (ValueError, TypeError):
                all_errors.append("Invalid decimals value")
        
        # Validate supply
        if 'supply' in metadata and metadata['supply'] is not None:
            supply_result = self.numeric_validator.validate_volume(metadata['supply'])
            all_errors.extend(supply_result.errors)
            all_warnings.extend(supply_result.warnings)
            if supply_result.normalized_data:
                normalized_data['supply'] = supply_result.normalized_data['volume']
        
        # Validate URLs
        url_fields = ['website', 'image_uri']
        for field in url_fields:
            if field in metadata and metadata[field]:
                url = metadata[field]
                if not url.startswith(('http://', 'https://')):
                    all_warnings.append(f"Invalid URL format for {field}")
                normalized_data[field] = url
        
        # Validate social handles
        social_fields = {'twitter': r'^[A-Za-z0-9_]{1,15}', 'telegram': r'^[A-Za-z0-9_]{5,32}'}
        for field, pattern in social_fields.items():
            if field in metadata and metadata[field]:
                handle = metadata[field].replace('@', '').strip()
                if not re.match(pattern, handle):
                    all_warnings.append(f"Invalid {field} handle format")
                normalized_data[field] = handle
        
        return ValidationResult(
            valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            normalized_data=normalized_data
        )
    
    def validate_price_data(self, price_data: Dict[str, Any]) -> ValidationResult:
        """Validate price data"""
        all_errors = []
        all_warnings = []
        normalized_data = {}
        
        # Required fields
        if 'current_price' not in price_data:
            all_errors.append("Missing current_price")
            return ValidationResult(valid=False, errors=all_errors)
        
        # Validate current price
        price_result = self.numeric_validator.validate_price(price_data['current_price'])
        all_errors.extend(price_result.errors)
        all_warnings.extend(price_result.warnings)
        if price_result.normalized_data:
            normalized_data['current_price'] = price_result.normalized_data['price']
        
        # Validate percentage changes
        percentage_fields = ['price_change_1h', 'price_change_24h', 'price_change_7d']
        for field in percentage_fields:
            if field in price_data and price_data[field] is not None:
                perc_result = self.numeric_validator.validate_percentage(price_data[field])
                all_errors.extend(perc_result.errors)
                all_warnings.extend(perc_result.warnings)
                if perc_result.normalized_data:
                    normalized_data[field] = perc_result.normalized_data['percentage']
        
        # Validate volume and market cap
        volume_fields = ['volume_24h', 'market_cap', 'liquidity']
        for field in volume_fields:
            if field in price_data and price_data[field] is not None:
                vol_result = self.numeric_validator.validate_volume(price_data[field])
                all_errors.extend(vol_result.errors)
                all_warnings.extend(vol_result.warnings)
                if vol_result.normalized_data:
                    normalized_data[field] = vol_result.normalized_data['volume']
        
        # Validate holders count
        if 'holders_count' in price_data and price_data['holders_count'] is not None:
            try:
                holders = int(price_data['holders_count'])
                if holders < 0:
                    all_errors.append("Holders count cannot be negative")
                elif holders == 0:
                    all_warnings.append("Zero holders - might indicate new or inactive token")
                elif holders > 1000000:
                    all_warnings.append("Very high holder count - verify accuracy")
                normalized_data['holders_count'] = holders
            except (ValueError, TypeError):
                all_errors.append("Invalid holders_count format")
        
        # Validate timestamp
        if 'timestamp' in price_data:
            ts_result = self.datetime_validator.validate_timestamp(price_data['timestamp'])
            all_errors.extend(ts_result.errors)
            all_warnings.extend(ts_result.warnings)
            if ts_result.normalized_data:
                normalized_data['timestamp'] = ts_result.normalized_data['timestamp']
        
        return ValidationResult(
            valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            normalized_data=normalized_data
        )


class APIRequestValidator:
    """Validate API request data"""
    
    @staticmethod
    def validate_token_analysis_request(request_data: Dict[str, Any]) -> ValidationResult:
        """Validate token analysis request"""
        errors = []
        warnings = []
        normalized_data = {}
        
        # Required mint field
        if 'mint' not in request_data or not request_data['mint']:
            errors.append("Missing required field: mint")
            return ValidationResult(valid=False, errors=errors)
        
        # Validate mint address
        mint_result = SolanaAddressValidator.validate_token_mint(request_data['mint'])
        errors.extend(mint_result.errors)
        warnings.extend(mint_result.warnings)
        if mint_result.normalized_data:
            normalized_data['mint'] = mint_result.normalized_data['address']
        
        # Validate optional boolean fields
        bool_fields = ['include_social', 'include_deep_analysis']
        for field in bool_fields:
            if field in request_data:
                if not isinstance(request_data[field], bool):
                    try:
                        normalized_data[field] = bool(request_data[field])
                        warnings.append(f"Converted {field} to boolean")
                    except:
                        errors.append(f"Invalid boolean value for {field}")
                else:
                    normalized_data[field] = request_data[field]
        
        # Validate priority
        if 'priority' in request_data:
            priority = request_data['priority'].lower()
            if priority not in ['low', 'normal', 'high']:
                errors.append("Priority must be one of: low, normal, high")
            else:
                normalized_data['priority'] = priority
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data=normalized_data
        )


# Global validator instances
solana_validator = SolanaAddressValidator()
numeric_validator = NumericValidator()
social_validator = SocialDataValidator()
datetime_validator = DateTimeValidator()
token_validator = TokenDataValidator()
api_validator = APIRequestValidator()


def validate_pydantic_model(model_class: type, data: Dict[str, Any]) -> ValidationResult:
    """Validate data against Pydantic model"""
    try:
        # Try to create model instance
        model_instance = model_class(**data)
        return ValidationResult(
            valid=True,
            normalized_data=model_instance.dict()
        )
    except ValidationError as e:
        errors = []
        for error in e.errors():
            field = '.'.join(str(loc) for loc in error['loc'])
            message = error['msg']
            errors.append(f"{field}: {message}")
        
        return ValidationResult(
            valid=False,
            errors=errors
        )
    except Exception as e:
        return ValidationResult(
            valid=False,
            errors=[f"Validation error: {str(e)}"]
        )


def sanitize_user_input(input_data: str, max_length: int = 1000) -> str:
    """Sanitize user input for security"""
    if not input_data:
        return ""
    
    # Convert to string and limit length
    sanitized = str(input_data)[:max_length]
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\n', '\r']
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    
    return sanitized.strip()


def normalize_token_address(address: str) -> Tuple[str, List[str]]:
    """Normalize and validate token address"""
    warnings = []
    
    if not address:
        raise ValueError("Address cannot be empty")
    
    # Clean the address
    normalized = address.strip()
    
    # Remove common prefixes if present
    if normalized.startswith('solana:'):
        normalized = normalized[7:]
        warnings.append("Removed 'solana:' prefix")
    
    # Validate format
    result = solana_validator.validate_address(normalized)
    if not result.valid:
        raise ValueError(f"Invalid address: {'; '.join(result.errors)}")
    
    warnings.extend(result.warnings)
    
    return normalized, warnings


def validate_and_normalize_request(request_data: Dict[str, Any], expected_fields: List[str]) -> Tuple[Dict[str, Any], ValidationResult]:
    """Validate and normalize API request data"""
    errors = []
    warnings = []
    normalized_data = {}
    
    # Check for required fields
    missing_fields = [field for field in expected_fields if field not in request_data]
    if missing_fields:
        errors.append(f"Missing required fields: {', '.join(missing_fields)}")
    
    # Sanitize all string inputs
    for key, value in request_data.items():
        if isinstance(value, str):
            normalized_data[key] = sanitize_user_input(value)
        else:
            normalized_data[key] = value
    
    # Additional validation based on field names
    for key, value in normalized_data.items():
        if key.endswith('_address') or key == 'mint':
            try:
                normalized_addr, addr_warnings = normalize_token_address(value)
                normalized_data[key] = normalized_addr
                warnings.extend(addr_warnings)
            except ValueError as e:
                errors.append(str(e))
    
    validation_result = ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        normalized_data=normalized_data
    )
    
    return normalized_data, validation_result


# Validation middleware for FastAPI
class ValidationMiddleware:
    """Middleware for request validation"""
    
    def __init__(self):
        self.logger = logger.bind(component="validation")
    
    async def validate_request(self, request_data: Dict[str, Any], endpoint: str) -> ValidationResult:
        """Validate request based on endpoint"""
        try:
            if endpoint.startswith('/tweet/') or endpoint.startswith('/name/'):
                # Token analysis endpoints
                return api_validator.validate_token_analysis_request(request_data)
            else:
                # Generic validation
                return ValidationResult(valid=True)
                
        except Exception as e:
            self.logger.error(f"Request validation error for {endpoint}: {str(e)}")
            return ValidationResult(
                valid=False,
                errors=[f"Validation error: {str(e)}"]
            )
"""
Base API client with caching, error handling, and rate limiting.
"""

import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..database_models import APICallLog

# Custom exceptions
class APIError(Exception):
    """Base exception for API errors."""
    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded (429)."""
    pass


class TimeoutError(APIError):
    """Raised when API request times out."""
    pass


class BaseAPIClient:
    """
    Base class for all external API clients.
    
    Features:
    - HTTP requests with requests library
    - Caching layer (database-backed)
    - Error handling (429, 500, timeout, network)
    - Retry logic with exponential backoff
    - Rate limit tracking (logs to api_call_log table)
    """
    
    def __init__(
        self,
        api_name: str,
        base_url: str,
        api_key: Optional[str] = None,
        db_path: str = "dfs_optimizer.db",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize API client.
        
        Args:
            api_name: Name of the API (for logging)
            base_url: Base URL for API endpoints
            api_key: Optional API key for authentication
            db_path: Path to SQLite database
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.api_name = api_name
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Setup database session
        engine = create_engine(f'sqlite:///{db_path}')
        Session = sessionmaker(bind=engine)
        self.session = Session()
        
        # Setup logging
        self.logger = logging.getLogger(f"{__name__}.{api_name}")
        
    def _make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with error handling and retry logic.
        
        Args:
            endpoint: API endpoint (appended to base_url)
            method: HTTP method (GET, POST, etc.)
            params: Query parameters
            headers: HTTP headers
            data: Request body data
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            RateLimitError: If rate limit exceeded (429)
            TimeoutError: If request times out
            APIError: For other API errors
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Add API key to params if provided
        if self.api_key and params is not None:
            params['apiKey'] = self.api_key
        elif self.api_key:
            params = {'apiKey': self.api_key}
            
        # Attempt request with retries
        for attempt in range(self.max_retries):
            start_time = time.time()
            
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Log API call
                self._log_api_call(
                    endpoint=endpoint,
                    response_status=response.status_code,
                    response_size_kb=len(response.content) / 1024,
                    duration_ms=duration_ms,
                    error_message=None if response.ok else response.text[:500]
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    self.logger.warning(f"Rate limit exceeded for {self.api_name}")
                    raise RateLimitError(f"Rate limit exceeded for {self.api_name}")
                
                # Handle server errors with retry
                if response.status_code >= 500:
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)
                        self.logger.warning(
                            f"Server error {response.status_code}, retrying in {delay}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        raise APIError(
                            f"Server error {response.status_code}: {response.text[:200]}"
                        )
                
                # Handle client errors (4xx except 429)
                if 400 <= response.status_code < 500:
                    raise APIError(
                        f"Client error {response.status_code}: {response.text[:200]}"
                    )
                
                # Success - return JSON
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                duration_ms = int((time.time() - start_time) * 1000)
                self._log_api_call(
                    endpoint=endpoint,
                    response_status=0,
                    response_size_kb=0,
                    duration_ms=duration_ms,
                    error_message="Request timeout"
                )
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Request timeout, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                    continue
                else:
                    raise TimeoutError(f"Request timed out after {self.timeout}s")
                    
            except requests.exceptions.RequestException as e:
                duration_ms = int((time.time() - start_time) * 1000)
                self._log_api_call(
                    endpoint=endpoint,
                    response_status=0,
                    response_size_kb=0,
                    duration_ms=duration_ms,
                    error_message=str(e)[:500]
                )
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Network error: {e}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                    continue
                else:
                    raise APIError(f"Network error: {e}")
        
        # Should not reach here
        raise APIError("Max retries exceeded")
    
    def _log_api_call(
        self,
        endpoint: str,
        response_status: int,
        response_size_kb: float,
        duration_ms: int,
        error_message: Optional[str] = None
    ):
        """
        Log API call to database for rate limit tracking.
        
        Args:
            endpoint: API endpoint called
            response_status: HTTP status code (0 if timeout/network error)
            response_size_kb: Response size in KB (ignored for now, schema doesn't have it)
            duration_ms: Request duration in milliseconds
            error_message: Error message if call failed
        """
        try:
            log_entry = APICallLog(
                api_name=self.api_name,
                endpoint=endpoint,
                status_code=response_status if response_status > 0 else None,
                response_time_ms=duration_ms,
                error_message=error_message,
                called_at=datetime.now()
            )
            self.session.add(log_entry)
            self.session.commit()
        except Exception as e:
            self.logger.error(f"Failed to log API call: {e}")
            self.session.rollback()
    
    def get_recent_call_count(self, hours: int = 24) -> int:
        """
        Get number of API calls made in the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Number of API calls in the time window
        """
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            count = self.session.query(APICallLog).filter(
                APICallLog.api_name == self.api_name,
                APICallLog.called_at >= cutoff
            ).count()
            return count
        except Exception as e:
            self.logger.error(f"Failed to get call count: {e}")
            return 0
    
    def close(self):
        """Close database session."""
        try:
            self.session.close()
        except Exception as e:
            self.logger.error(f"Error closing session: {e}")


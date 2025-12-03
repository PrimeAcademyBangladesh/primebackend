"""Response utilities and DRF exception handler helpers.

This module provides a canonical API response envelope and a DRF
exception handler that normalizes errors into the same {success, message,
data} structure used across the API.

Keep implementations small and focused so they are easy to test and
document. These functions are imported widely by views and settings.
"""

import sys
import traceback

from rest_framework import status
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.views import exception_handler


def api_response(success: bool, message: str, data=None, status_code=status.HTTP_200_OK):
    """
    Reusable API response wrapper for consistent frontend consumption.
    Args:
        success (bool): Indicates if the request was successful.
        message (str): Human-readable message for the frontend.
        data (dict or list, optional): The data payload. Defaults to empty dict.
        status_code (int, optional): HTTP status code. Defaults to 200.
    Returns:
        Response: DRF Response object with standardized structure.
    """
    if data is None:
        data = {}
    return Response({"success": success, "message": message, "data": data}, status=status_code)



def custom_exception_handler(exc, context):
    """
    Custom exception handler that formats all errors to match api_response format.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Extract clean error message from nested structures
        def extract_clean_message(error_data):
            """Recursively extract clean error message from nested errors."""
            if isinstance(error_data, list) and error_data:
                # Get first item from list
                return extract_clean_message(error_data[0])
            elif isinstance(error_data, dict) and error_data:
                # Get first value from dictionary and recurse
                first_value = next(iter(error_data.values()))
                return extract_clean_message(first_value)
            elif hasattr(error_data, 'code') and hasattr(error_data, 'detail'):
                # Handle ErrorDetail objects - return just the string
                return str(error_data)
            else:
                # Return string representation
                return str(error_data)
        
        # Extract message from exception detail or response data
        if hasattr(exc, 'detail'):
            message = extract_clean_message(exc.detail)
        else:
            message = extract_clean_message(response.data)
        
        # Determine appropriate status code
        status_code = response.status_code
        
        # For validation errors in login, use 401 instead of 400
        if isinstance(exc, ValidationError) and 'login' in str(context['request'].path):
            status_code = status.HTTP_401_UNAUTHORIZED
        
        return api_response(False, message, response.data, status_code)
    
    # For unhandled exceptions
    # Print exception traceback to stdout for debugging in tests (temporary)
    try:
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info)
    except Exception:
        pass
    return api_response(
        False,
        f"An internal server error occurred: {str(exc)}",
        {},
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


"""
Session & Cache Security Middleware
Prevents browser caching of sensitive pages to ensure users cannot access them via back button
"""
from django.utils.deprecation import MiddlewareMixin


class NoUserCacheMiddleware(MiddlewareMixin):
    """
    Prevents caching of authenticated user pages to ensure session security.
    Users cannot access authenticated pages via browser back button after logout.
    """
    
    def process_response(self, request, response):
        """Add cache control headers to prevent unauthorized access via back button"""
        
        # If user is authenticated, prevent caching
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            # Prevent compression attacks
            response['X-Content-Type-Options'] = 'nosniff'
        
        # Also prevent caching on login/logout pages
        if request.path in ['/login/', '/logout/', '/']:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response

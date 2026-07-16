from django.conf import settings


class NoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.DEBUG:
            if request.path.startswith(("/static/", "/media/")):
                response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"
            elif response.get("Content-Type", "").startswith("text/html"):
                response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"
        return response

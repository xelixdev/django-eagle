from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from eagle.config import is_enabled
from eagle.unused import begin_request, end_request


class EagleWarnUnusedMiddleware(MiddlewareMixin):
    """Django middleware that scopes Eagle's access tracking to a single request/response cycle."""

    def process_request(self, request: HttpRequest) -> None:
        """
        Activate Eagle tracking at the start of each request.

        Args:
            request: The incoming Django HTTP request.
        """
        if is_enabled():
            begin_request()

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Emit unused-relation warnings and deactivate tracking before returning the response.

        Args:
            request: The Django HTTP request being processed.
            response: The outgoing HTTP response.

        Returns:
            The unmodified *response* object.
        """
        if is_enabled():
            end_request()
        return response

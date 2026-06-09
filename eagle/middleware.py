from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from eagle.config import is_enabled
from eagle.unused import begin_request, end_request


class EagleWarnUnusedMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest) -> None:
        if is_enabled():
            begin_request()

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        if is_enabled():
            end_request()
        return response

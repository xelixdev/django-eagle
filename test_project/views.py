import contextlib

from django.db.models import Prefetch
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from eagle import mark_considered, may_access

from test_project.models import Eagle
from test_project.serializers import EagleSerializer


def _csv(value: str | None) -> list[str]:
    return [item for item in (value or "").split(",") if item]


class EagleView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        params = request.query_params
        considered = _csv(params.get("mark_considered"))

        if considered and params.get("mark_before") == "1":
            mark_considered(Eagle, *considered)

        queryset = Eagle.objects.all()

        for field in _csv(params.get("select_related")):
            queryset = queryset.select_related(field)

        for field in _csv(params.get("prefetch_related")):
            queryset = queryset.prefetch_related(field)

        to_attr_spec = params.get("prefetch_to_attr")
        to_attr_name = None
        if to_attr_spec:
            lookup, _, to_attr_name = to_attr_spec.partition(":")
            queryset = queryset.prefetch_related(Prefetch(lookup, to_attr=to_attr_name))

        eagle = queryset.get(pk=pk)

        data = EagleSerializer(
            eagle, context={"access": _csv(params.get("access")), "to_attr": to_attr_name}
        ).data

        if considered and params.get("mark_before") != "1":
            mark_considered(Eagle, *considered)

        if guarded := _csv(params.get("may_access")):
            self._run_may_access(guarded, params)

        return Response(data)

    def _run_may_access(self, fields: list[str], params) -> None:
        raises = params.get("may_access_raise") == "1"

        @may_access(Eagle, *fields)
        def consumer() -> None:
            if raises:
                msg = "boom"
                raise RuntimeError(msg)

        if params.get("may_access_call") == "1":
            with contextlib.suppress(RuntimeError):
                consumer()

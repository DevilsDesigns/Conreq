import json

from conreq.core.user_requests.models import UserRequest
from conreq.core.tmdb.discovery import TmdbDiscovery
from conreq.core.arrs.sonarr_radarr import ArrManager
from conreq.utils import log
from conreq.utils.testing import performance_metrics
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.template import loader
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from .helpers import generate_requests_cards, radarr_request, sonarr_request

_logger = log.get_logger(__name__)

# Days, Hours, Minutes, Seconds
INVITE_CODE_DURATION = 7 * 24 * 60 * 60


@login_required
@performance_metrics()
def request_content(request):
    # User submitted a new request
    if request.method == "POST":
        request_parameters = json.loads(request.body.decode("utf-8"))
        log.handler(
            "Request received: " + str(request_parameters),
            log.INFO,
            _logger,
        )

        content_manager = ArrManager()
        content_discovery = TmdbDiscovery()

        # TV show was requested
        if request_parameters["content_type"] == "tv":
            # Try to obtain a TVDB ID (from params or fetch it from TMDB)
            tmdb_id = request_parameters["tmdb_id"]
            tvdb_id = content_discovery.get_external_ids(tmdb_id, "tv").get("tvdb_id")

            # Request the show by the TVDB ID
            if tvdb_id:
                sonarr_request(
                    tvdb_id,
                    tmdb_id,
                    request,
                    request_parameters,
                    content_manager,
                    content_discovery,
                )

            else:
                return HttpResponseForbidden()

        # Movie was requested
        elif request_parameters["content_type"] == "movie":
            tmdb_id = request_parameters["tmdb_id"]
            radarr_request(tmdb_id, request, content_manager, content_discovery)

        # The request succeeded
        return JsonResponse({"success": True})

    return HttpResponseForbidden()


@cache_page(1)
@vary_on_cookie
@login_required
@performance_metrics()
def my_requests(request):
    user_requests = (
        UserRequest.objects.filter(requested_by=request.user)
        .order_by("id")
        .reverse()
        .values()
    )
    all_cards = generate_requests_cards(user_requests)
    context = {"all_cards": all_cards, "page_name": "My Requests"}
    template = loader.get_template("viewport/requests.html")
    return HttpResponse(template.render(context, request))


@cache_page(1)
@login_required
@performance_metrics()
def all_requests(request):
    user_requests = (
        UserRequest.objects.all()
        .order_by("id")
        .reverse()
        .values(
            "content_id",
            "content_type",
            "requested_by__username",
        )
    )
    all_cards = generate_requests_cards(user_requests)
    context = {"all_cards": all_cards, "page_name": "All Requests"}
    template = loader.get_template("viewport/requests.html")
    return HttpResponse(template.render(context, request))

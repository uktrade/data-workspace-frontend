from django.utils.cache import add_never_cache_headers


def disable_client_side_caching(get_response):
    def middleware(request):
        response = get_response(request)
        add_never_cache_headers(response)
        return response

    return middleware

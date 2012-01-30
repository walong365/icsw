from django.http import HttpResponseForbidden

def require_POST_params(params):
    """
    Decorator that requires a POST request and certain *params* to be present.
    """
    def _decorator(func):

        def _wrapper(request, *args, **kwargs):
            if request.method != "POST":
                return HttpResponseForbidden("Only POST allowed")
            if isinstance(params, (tuple, list, set)):
                for i in params:
                    if i not in request.POST:
                        return HttpResponseForbidden("Missing parameter %s" % i)
            else:
                if params not in request.POST:
                    return HttpResponseForbidden("Missing parameter %s" % params)
            return func(request, *args, **kwargs)
        return _wrapper

    return _decorator
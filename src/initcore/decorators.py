from django.http import HttpResponseForbidden

def require_POST_params(params):
    """
    Decorator that requires a POST request and certain *params* to be present.
    """
    def _decorator(func):
        
        def _wrapper(request, *args, **kwargs):
            if request.method != "POST":
                return HttpResponseForbidden("Only POST allowed")
            for i in params:
                if i not in request.POST:
                    return HttpResponseForbidden("Missing parameter %s" % i)
            return func(request, *args, **kwargs)
        return _wrapper 
    
    return _decorator
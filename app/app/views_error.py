from django.shortcuts import (
    render,
)


def public_error_404_html_view(request, exception=None):
    return render(request, 'error_404.html', status=404)


def public_error_403_html_view(request, exception=None):
    return render(request, 'error_403.html', status=403)


def public_error_500_html_view(request):
    message = request.GET.get('message', None)

    return render(request, 'error_500.html', {'message': message}, status=500)

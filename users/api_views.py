import json

from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework_simplejwt.tokens import RefreshToken

from learning_logs.api_views import api_login_required


@csrf_exempt
@require_http_methods(['POST'])
def register_api(request):
    if not (request.content_type and request.content_type.startswith('application/json')):
        return JsonResponse({'error': 'Expected application/json payload.'}, status=400)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    form = UserCreationForm(data=data)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)

    user = form.save()
    refresh = RefreshToken.for_user(user)

    return JsonResponse(
        {
            'user': {
                'id': user.id,
                'username': user.username,
            },
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
        },
        status=201,
    )


@api_login_required
@require_http_methods(['GET'])
def current_user(request):
    return JsonResponse(
        {
            'user': {
                'id': request.user.id,
                'username': request.user.username,
            }
        }
    )

ALLOWED_HOSTS = ['*', '.amazonaws.com', 'localhost', '127.0.0.1']
print("DEBUG: ALLOWED_HOSTS =", ALLOWED_HOSTS)

class DebugHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        print("DEBUG: ALLOWED_HOSTS =", ALLOWED_HOSTS)

    def __call__(self, request):
        return self.get_response(request)

MIDDLEWARE = [
    'notekeeper.settings.DebugHostMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
] 
import json
import time
import urllib.request
import sys

base = 'http://127.0.0.1:8000'
question = 'ما هي شروط القبول في الجامعة؟'
email = f'phase6.{int(time.time())}@example.com'
password = 'super-secure-password'

def post(path, payload, headers=None):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', **(headers or {} )},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode('utf-8'))

try:
    post('/auth/register', {'email': email, 'password': password, 'full_name': 'Phase 6 Smoke'})
    login = post('/auth/login', {'email': email, 'password': password})
    chat = post('/chat', {'question': question, 'top_k': 4}, {'Authorization': 'Bearer ' + login['access_token']})
    print(json.dumps({'http': 200, 'language': chat.get('language'), 'sourceCount': len(chat.get('sources', [])), 'answerPrefix': chat.get('answer', '')[:120]}, ensure_ascii=False))
except urllib.error.HTTPError as e:
    print(json.dumps({'http': e.code, 'error': str(e)}, ensure_ascii=False))
    sys.exit(1)
except Exception as e:
    print(json.dumps({'error': str(e)}, ensure_ascii=False))
    sys.exit(1)

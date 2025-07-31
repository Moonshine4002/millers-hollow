import httpx


def sync_request() -> dict:
    data = {'name': 'name', 'controller': 'human'}
    try:
        response = httpx.post('http://localhost:8000/register', json=data)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return {}


print(sync_request())

import requests

try:
    response = requests.get('http://127.0.0.1:8888', timeout=5)
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'text/html' in response.headers.get('Content-Type', ''):
        print("The response contains HTML.")
    else:
        print("The response does not contain HTML.")
    print("\nResponse Preview:")
    print(response.text[:500])
except requests.exceptions.RequestException as e:
    print(f"Error: {e}")

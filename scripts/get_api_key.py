import requests

url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

payload={
  'scope': 'GIGACHAT_API_PERS'
}
headers = {
  'Content-Type': 'application/x-www-form-urlencoded',
  'Accept': 'application/json',
  'RqUID': 'aa294005-e6e2-45e9-b384-d07dce9a21f1',
  'Authorization': 'Basic <auth_token>'
}

response = requests.request("POST", url, headers=headers, data=payload, verify=False)

print(response.text)
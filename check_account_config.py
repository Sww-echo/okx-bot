
import os
import asyncio
from dotenv import load_dotenv
from okx import Account

load_dotenv()

api_key = os.getenv('OKX_DEMO_API_KEY')
secret_key = os.getenv('OKX_DEMO_SECRET_KEY')
passphrase = os.getenv('OKX_DEMO_PASSPHRASE')

account_api = Account.AccountAPI(api_key, secret_key, passphrase, flag='1')

result = account_api.get_account_config()
print(f"Account Config: {result}")

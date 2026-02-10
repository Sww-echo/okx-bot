
import os
from dotenv import load_dotenv
from okx import MarketData

load_dotenv()

api_key = os.getenv('OKX_DEMO_API_KEY')
secret_key = os.getenv('OKX_DEMO_SECRET_KEY')
passphrase = os.getenv('OKX_DEMO_PASSPHRASE')

market_api = MarketData.MarketAPI(api_key, secret_key, passphrase, flag='1')

result = market_api.get_tickers(instType='SWAP')
if result['code'] == '0':
    print("Available SWAP tickers:")
    for ticker in result['data']:
        if 'OKB' in ticker['instId']:
            print(ticker['instId'])
else:
    print(f"Error: {result}")

import aiohttp
import asyncio
import logging
from config import ETHERSCAN_API_KEY, ETHERSCAN_API_URL

logging.basicConfig(level=logging.INFO)

class EthereumClient:
    def __init__(self):
        self.base_url = ETHERSCAN_API_URL
        self.api_key = ETHERSCAN_API_KEY

    async def _make_request(self, params):
        params['apikey'] = self.api_key
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    if data.get('status') == '0':
                        logging.error(f"API request failed: {data.get('message')}")
                        return None
                    return data.get('result')
        except aiohttp.ClientError as e:
            logging.error(f"API request failed: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return None

    async def get_latest_block_number(self):
        params = {
            "module": "proxy",
            "action": "eth_blockNumber"
        }
        result = await self._make_request(params)
        return int(result, 16) if result else None

    async def get_block_by_number(self, block_number):
        params = {
            "module": "proxy",
            "action": "eth_getBlockByNumber",
            "tag": hex(block_number),
            "boolean": "true"
        }
        return await self._make_request(params)

    async def get_transaction_by_hash(self, tx_hash):
        params = {
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash
        }
        return await self._make_request(params)

    async def get_transaction_receipt(self, tx_hash):
        params = {
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash
        }
        return await self._make_request(params)

    async def get_gas_price(self):
        params = {
            "module": "gastracker",
            "action": "gasoracle"
        }
        result = await self._make_request(params)
        return float(result['SafeGasPrice']) if result else None

    async def get_average_gas_price(self):
        params = {
            "module": "gastracker",
            "action": "gasoracle",
        }
        result = await self._make_request(params)
        return float(result['SafeGasPrice']) if result else None

    async def get_jco_price(self):
        # This is a placeholder. Implement actual logic to get JCO price.
        # You may need to use a different API or data source for JCO price.
        return 1.23  # Replace with actual JCO price fetching logic

    async def get_jco_price_change(self):
        # This is a placeholder. Implement actual logic to get JCO price change.
        # You may need to use a different API or data source for JCO price change.
        return 0.05  # Replace with actual JCO price change fetching logic

    async def get_balance(self, address, block="latest"):
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": block,
        }
        result = await self._make_request(params)
        if result:
            balance_wei = int(result)
            balance_eth = balance_wei / 1e18
            return balance_eth
        return None

async def get_transaction_value(self, tx_hash):
    # Fetch transaction data
    tx_data = await self.get_transaction_by_hash(tx_hash)
    if not tx_data:
        logging.error(f"Transaction not found: {tx_hash}")
        return None

    # Extract transaction value in Wei
    value_wei = int(tx_data.get('value', 0), 16)  # Value in Wei

    # Convert Wei to Ether (1 Ether = 1e18 Wei)
    value_eth = value_wei / 1e18  # Value in Ether
    return value_eth


async def get_transaction_state_changes(tx_hash):
    client = EthereumClient()
    logging.info(f"Fetching state changes for transaction: {tx_hash}")
    
    try:
        # Fetch transaction data
        tx_data = await client.get_transaction_by_hash(tx_hash)
        if not tx_data:
            logging.error(f"Transaction not found: {tx_hash}")
            return None

        receipt_data = await client.get_transaction_receipt(tx_hash)
        if not receipt_data:
            logging.error(f"Transaction receipt not found: {tx_hash}")
            return None

        # Extract addresses
        from_address = tx_data['from']
        to_address = tx_data['to']
        block_number = int(tx_data['blockNumber'], 16)

        # Fetch balances before and after in parallel
        async def get_balances(address):
            before = await client.get_balance(address, block=hex(block_number - 1))
            after = await client.get_balance(address, block=hex(block_number))
            return address, before, after

        # Fetch all balances concurrently
        tasks = [get_balances(addr) for addr in [from_address, to_address]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        state_changes = []
        for result in results:
            if isinstance(result, Exception):
                logging.error(f"Error fetching balances: {result}")
                continue
                
            address, balance_before, balance_after = result
            if balance_before is not None and balance_after is not None:
                state_changes.append({
                    "address": address,
                    "before": f"{balance_before:.6f} ETH",
                    "after": f"{balance_after:.6f} ETH",
                    "difference": f"{(balance_after - balance_before):.6f} ETH"
                })

        return state_changes if state_changes else []

    except Exception as e:
        logging.error(f"Error in get_transaction_state_changes: {e}")
        return []
    
async def main():
    client = EthereumClient()
    
    latest_block_number = await client.get_latest_block_number()
    print(f"Latest Block Number: {latest_block_number or 'N/A'}")
    
    gas_price = await client.get_gas_price()
    print(f"Gas Price: {gas_price or 'N/A'} Gwei")
    
    jco_price = await client.get_jco_price()
    print(f"JCO Price: {jco_price or 'N/A'} USD")
    
    address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"  # Example address
    balance_latest = await client.get_balance(address)
    print(f"Current Balance: {balance_latest:.6f} ETH" if balance_latest is not None else "Current Balance: N/A")
    
    if latest_block_number:
        historical_block_number = latest_block_number - 100
        balance_historical = await client.get_balance(address, block=hex(historical_block_number))
        print(f"Balance at Block {historical_block_number}: {balance_historical:.6f} ETH" if balance_historical is not None else f"Balance at Block {historical_block_number}: N/A")
    else:
        print("Unable to fetch historical balance due to missing latest block number")

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

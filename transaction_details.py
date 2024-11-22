import asyncio
from datetime import datetime
import logging
from ethereum_client import EthereumClient
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def calculate_gas_metrics(client: EthereumClient, tx_data: Dict[str, Any], receipt_data: Dict[str, Any]) -> Dict[str, Any]:
    avg_gas_price = await client.get_average_gas_price()
    if not avg_gas_price:
        return {"error": "Failed to fetch average gas price"}

    gas_price = int(tx_data['gasPrice'], 16) / 1e9  # Convert to Gwei
    gas_used = int(receipt_data['gasUsed'], 16)
    gas_limit = int(tx_data['gas'], 16)

    # Calculate gas metrics
    gas_efficiency = (gas_used / gas_limit) * 100
    price_difference = ((gas_price - avg_gas_price) / avg_gas_price) * 100
    
    # Calculate risk score (0-100)
    risk_score = min(100, max(0, (gas_efficiency * 0.5) + (abs(price_difference) * 0.5)))

    return {
        "gasUsed": gas_used,
        "gasLimit": gas_limit,
        "gasPrice": f"{gas_price:.2f}",
        "avgGasPrice": avg_gas_price,
        "gasEfficiency": f"{gas_efficiency:.2f}%",
        "priceDifference": f"{price_difference:+.2f}%",
        "riskScore": f"{risk_score:.2f}"
    }

async def get_transaction_details(tx_hash):
    client = EthereumClient()
    logging.info(f"Fetching details for transaction: {tx_hash}")
    tx_data = await client.get_transaction_by_hash(tx_hash)

    if not tx_data:
        logging.error(f"Could not retrieve transaction data for hash {tx_hash}")
        return None

    receipt_data = await client.get_transaction_receipt(tx_hash)

    if not receipt_data:
        logging.error(f"Could not retrieve receipt data for hash {tx_hash}")
        return None

    block_number = int(tx_data["blockNumber"], 16)
    block_data = await client.get_block_by_number(block_number)

    if not block_data:
        logging.error(f"Could not retrieve block data for number {block_number}")
        return None

    value_in_ether = float(int(tx_data["value"], 16)) / 1e18
    gas_price_in_gwei = float(int(tx_data["gasPrice"], 16)) / 1e9
    gas_used = int(receipt_data["gasUsed"], 16)
    transaction_fee = (gas_used * gas_price_in_gwei) / 1e9
    timestamp = datetime.fromtimestamp(int(block_data["timestamp"], 16))

    gas_metrics = await calculate_gas_metrics(client, tx_data, receipt_data)

    transaction_details = {
        "Transaction Hash": tx_data["hash"],
        "Status": "Success" if receipt_data["status"] == "0x1" else "Failure",
        "Block": block_number,
        "Timestamp": timestamp.strftime("%b-%d-%Y %I:%M:%S %p +UTC"),
        "From": tx_data["from"],
        "Interacted With (To)": tx_data["to"],
        "Value": f"{value_in_ether:.6f} ETH",
        "Transaction Fee": f"{transaction_fee:.6f} ETH",
        "Gas Used": f"{gas_used}",
        "Gas Price": f"{gas_price_in_gwei:.2f} Gwei",
        "Gas Metrics": gas_metrics
    }

    return transaction_details

async def get_latest_transactions(num_transactions=1):
    client = EthereumClient()
    latest_block_number = await client.get_latest_block_number()

    if latest_block_number is None:
        logging.error("Could not retrieve latest block number")
        return []

    logging.info(f"Latest block number: {latest_block_number}")

    latest_block = await client.get_block_by_number(latest_block_number)

    if latest_block is None or "transactions" not in latest_block:
        logging.error(f"Could not retrieve transactions for block number {latest_block_number}")
        return []

    logging.info(f"Number of transactions in the latest block: {len(latest_block['transactions'])}")

    transactions = []
    for tx in latest_block["transactions"][-num_transactions:]:
        logging.info(f"Processing transaction hash: {tx['hash']}")
        transaction = await get_transaction_details(tx['hash'])
        if transaction is not None:
            transactions.append(transaction)
        else:
            logging.error(f"Could not retrieve details for transaction {tx['hash']}")

    logging.info(f"Total transactions processed: {len(transactions)}")
    return transactions

async def get_transaction_state_changes(tx_hash):
    client = EthereumClient()
    logging.info(f"Fetching state changes for transaction: {tx_hash}")
    tx_data = await client.get_transaction_by_hash(tx_hash)
    receipt_data = await client.get_transaction_receipt(tx_hash)

    if not tx_data or not receipt_data:
        logging.error(f"Could not retrieve transaction data or receipt for hash {tx_hash}")
        return None

    from_address = tx_data['from']
    to_address = tx_data['to']
    block_number = int(tx_data['blockNumber'], 16)

    from_balance_before = await client.get_balance(from_address, block_number - 1)
    from_balance_after = await client.get_balance(from_address, block_number)
    to_balance_before = await client.get_balance(to_address, block_number - 1)
    to_balance_after = await client.get_balance(to_address, block_number)

    value = int(tx_data['value'], 16) / 1e18
    gas_used = int(receipt_data['gasUsed'], 16)
    gas_price = int(tx_data['gasPrice'], 16) / 1e18
    transaction_fee = gas_used * gas_price

    state_changes = [
        {
            "address": from_address,
            "before": f"{from_balance_before:.6f}",
            "after": f"{from_balance_after:.6f}",
            "difference": f"{(from_balance_after - from_balance_before):.6f}",
        },
        {
            "address": to_address,
            "before": f"{to_balance_before:.6f}",
            "after": f"{to_balance_after:.6f}",
            "difference": f"{(to_balance_after - to_balance_before):.6f}",
        }
    ]

    return state_changes

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
    latest_transactions = await get_latest_transactions()
    if latest_transactions:
        print("Latest Transaction:")
        for transaction in latest_transactions:
            print(transaction)
    else:
        print("No transactions found.")

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

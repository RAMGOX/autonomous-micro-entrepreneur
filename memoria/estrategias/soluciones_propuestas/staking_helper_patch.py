"""
Web3Helper Extension for StakingYield
Bounty Issue #2: Robinhood EVM MCP (50,000 $ROBIN_MCP)
Methods: stake_tokens, unstake_tokens, claim_staking_rewards, get_staking_info
Operator Wallet: 0x02c1F87F514493F359Afc0B3ff6b587434770361
"""

STAKING_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "stake", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "unstake", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "claimReward", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "totalStaked", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}], "name": "stakedBalance", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}], "name": "accumulatedRewards", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
]

class StakingWeb3Mixin:
    async def stake_tokens(self, staking_address: str, amount_wei: int):
        account = self.get_account()
        contract = self.w3.eth.contract(address=self.w3.to_checksum_address(staking_address), abi=STAKING_ABI)
        nonce = self.w3.eth.get_transaction_count(account.address)
        tx = contract.functions.stake(amount_wei).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": self.network_config["chain_id"]
        })
        tx_hash = await self.sign_and_send_transaction(tx)
        return await self.wait_for_confirmation(tx_hash)

    async def unstake_tokens(self, staking_address: str, amount_wei: int):
        account = self.get_account()
        contract = self.w3.eth.contract(address=self.w3.to_checksum_address(staking_address), abi=STAKING_ABI)
        nonce = self.w3.eth.get_transaction_count(account.address)
        tx = contract.functions.unstake(amount_wei).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": self.network_config["chain_id"]
        })
        tx_hash = await self.sign_and_send_transaction(tx)
        return await self.wait_for_confirmation(tx_hash)

    async def claim_staking_rewards(self, staking_address: str):
        account = self.get_account()
        contract = self.w3.eth.contract(address=self.w3.to_checksum_address(staking_address), abi=STAKING_ABI)
        nonce = self.w3.eth.get_transaction_count(account.address)
        tx = contract.functions.claimReward().build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": self.network_config["chain_id"]
        })
        tx_hash = await self.sign_and_send_transaction(tx)
        return await self.wait_for_confirmation(tx_hash)

    def get_staking_info(self, staking_address: str, user_address: str):
        contract = self.w3.eth.contract(address=self.w3.to_checksum_address(staking_address), abi=STAKING_ABI)
        total = contract.functions.totalStaked().call()
        user_staked = contract.functions.stakedBalance(self.w3.to_checksum_address(user_address)).call()
        rewards = contract.functions.accumulatedRewards(self.w3.to_checksum_address(user_address)).call()
        return {
            "total_staked": total,
            "user_staked": user_staked,
            "accumulated_rewards": rewards
        }

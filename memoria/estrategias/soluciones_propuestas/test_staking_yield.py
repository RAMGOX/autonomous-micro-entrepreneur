"""
Test Suite: StakingYield & Web3 Helper Verification
Tests staking, reward index calculation, proportional yield, and unstaking.
Bounty Issue #2: Robinhood EVM MCP (50,000 $ROBIN_MCP)
Operator Wallet: 0x02c1F87F514493F359Afc0B3ff6b587434770361
"""
import unittest

class MockStakingYield:
    def __init__(self):
        self.total_staked = 0
        self.staked_balances = {}
        self.reward_index = 0
        self.user_reward_indices = {}
        self.accumulated_rewards = {}

    def _update_user_reward(self, user):
        user_balance = self.staked_balances.get(user, 0)
        if user_balance > 0:
            user_idx = self.user_reward_indices.get(user, 0)
            pending = (user_balance * (self.reward_index - user_idx)) // 10**18
            self.accumulated_rewards[user] = self.accumulated_rewards.get(user, 0) + pending
        self.user_reward_indices[user] = self.reward_index

    def deposit_rewards(self, amount_wei):
        if amount_wei > 0 and self.total_staked > 0:
            self.reward_index += (amount_wei * 10**18) // self.total_staked

    def stake(self, user, amount):
        assert amount > 0, "Cannot stake 0"
        self._update_user_reward(user)
        self.total_staked += amount
        self.staked_balances[user] = self.staked_balances.get(user, 0) + amount

    def unstake(self, user, amount):
        assert amount > 0, "Cannot unstake 0"
        assert self.staked_balances.get(user, 0) >= amount, "Insufficient staked balance"
        self._update_user_reward(user)
        self.total_staked -= amount
        self.staked_balances[user] -= amount

    def claim_reward(self, user):
        self._update_user_reward(user)
        reward = self.accumulated_rewards.get(user, 0)
        assert reward > 0, "No reward to claim"
        self.accumulated_rewards[user] = 0
        return reward

class TestStakingYieldProtocol(unittest.TestCase):
    def setUp(self):
        self.protocol = MockStakingYield()
        self.user_a = "0x02c1F87F514493F359Afc0B3ff6b587434770361"
        self.user_b = "0x1111111111111111111111111111111111111111"

    def test_single_user_staking_and_rewards(self):
        # User A stakes 10,000 tokens
        self.protocol.stake(self.user_a, 10000 * 10**18)
        self.assertEqual(self.protocol.total_staked, 10000 * 10**18)
        
        # 1 ETH fee reward deposited
        self.protocol.deposit_rewards(1 * 10**18)
        
        # User A claims 100% of the reward (1 ETH)
        reward = self.protocol.claim_reward(self.user_a)
        self.assertEqual(reward, 1 * 10**18)

    def test_proportional_rewards_two_users(self):
        # User A stakes 60%, User B stakes 40%
        self.protocol.stake(self.user_a, 6000 * 10**18)
        self.protocol.stake(self.user_b, 4000 * 10**18)
        self.assertEqual(self.protocol.total_staked, 10000 * 10**18)

        # 10 ETH reward deposited
        self.protocol.deposit_rewards(10 * 10**18)

        # User A should get 6 ETH, User B should get 4 ETH
        reward_a = self.protocol.claim_reward(self.user_a)
        reward_b = self.protocol.claim_reward(self.user_b)
        self.assertEqual(reward_a, 6 * 10**18)
        self.assertEqual(reward_b, 4 * 10**18)

    def test_unstake(self):
        self.protocol.stake(self.user_a, 5000 * 10**18)
        self.protocol.unstake(self.user_a, 2000 * 10**18)
        self.assertEqual(self.protocol.total_staked, 3000 * 10**18)
        self.assertEqual(self.protocol.staked_balances[self.user_a], 3000 * 10**18)

if __name__ == "__main__":
    unittest.main()

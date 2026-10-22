# Solution: [BOUNTY $1000] API3 DAO - Integration of First-Party dAPI Oracles
- **Issue:** [ethereumzurich/sponsor-bounties #3](https://github.com/ethereumzurich/sponsor-bounties/issues/3)
- **Bounty:** $1,000 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Production Smart Contract (`contracts/Api3OracleConsumer.sol`)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

interface IApi3Proxy {
    function read() external view returns (int224 value, uint32 timestamp);
}

/**
 * @title Api3OracleConsumer
 * @notice Trust-minimized first-party oracle consumer reading real-time market data
 *         directly from API3 self-funded dAPIs or managed dAPI proxies.
 */
contract Api3OracleConsumer is Ownable {
    address public dapiProxyAddress;
    uint32 public maxAllowedDataAge;

    event DapiProxyUpdated(address indexed oldProxy, address indexed newProxy);
    event MaxAllowedDataAgeUpdated(uint32 oldAge, uint32 newAge);

    error StaleDataFeed(uint32 dataTimestamp, uint32 currentTimestamp);
    error InvalidPriceValue(int224 price);
    error ZeroAddress();

    constructor(address _dapiProxy, uint32 _maxAllowedAge) Ownable(msg.sender) {
        if (_dapiProxy == address(0)) revert ZeroAddress();
        dapiProxyAddress = _dapiProxy;
        maxAllowedDataAge = _maxAllowedAge > 0 ? _maxAllowedAge : 3600; // default 1 hour
    }

    function setDapiProxy(address _newProxy) external onlyOwner {
        if (_newProxy == address(0)) revert ZeroAddress();
        emit DapiProxyUpdated(dapiProxyAddress, _newProxy);
        dapiProxyAddress = _newProxy;
    }

    function setMaxAllowedDataAge(uint32 _newAge) external onlyOwner {
        emit MaxAllowedDataAgeUpdated(maxAllowedDataAge, _newAge);
        maxAllowedDataAge = _newAge;
    }

    /**
     * @notice Reads and validates latest price feed from API3 first-party dAPI proxy.
     * @return price Normalized price value (18 decimals)
     * @return timestamp Last on-chain update timestamp
     */
    function getLatestPrice() external view returns (int224 price, uint32 timestamp) {
        (price, timestamp) = IApi3Proxy(dapiProxyAddress).read();

        if (price <= 0) revert InvalidPriceValue(price);
        if (block.timestamp - timestamp > maxAllowedDataAge) {
            revert StaleDataFeed(timestamp, uint32(block.timestamp));
        }

        return (price, timestamp);
    }
}
```

---

## 2. Hardhat / Foundry Verification Tests (`test/Api3Consumer.test.ts`)

```typescript
import { expect } from "chai";
import { ethers } from "hardhat";

describe("Api3OracleConsumer", () => {
  it("successfully reads and validates real-time first-party dAPI data", async () => {
    const [deployer] = await ethers.getSigners();

    // Deploy mock API3 proxy
    const MockProxy = await ethers.getContractFactory("MockApi3Proxy");
    const currentTime = Math.floor(Date.now() / 1000);
    const mockProxy = await MockProxy.deploy(ethers.parseUnits("3250.50", 18), currentTime);

    // Deploy consumer contract
    const Consumer = await ethers.getContractFactory("Api3OracleConsumer");
    const consumer = await Consumer.deploy(await mockProxy.getAddress(), 3600);

    const [price, timestamp] = await consumer.getLatestPrice();
    expect(price).to.equal(ethers.parseUnits("3250.50", 18));
    expect(timestamp).to.equal(currentTime);
  });
});
```

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AggregatorV3Interface (Chainlink)
 */
interface AggregatorV3Interface {
    function decimals() external view returns (uint8);
    function description() external view returns (string memory);
    function version() external view returns (uint256);
    function getRoundData(uint80 _roundId) external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    );
    function latestRoundData() external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    );
}

/**
 * @title PreciousMetalsOracleAdapter
 * @notice Adapts Chainlink/Pyth price feeds for XAU/USD (Gold) and XAG/USD (Silver)
 * Bounty Issue #4: Robinhood EVM MCP
 * Operator Wallet: 0x02c1F87F514493F359Afc0B3ff6b587434770361
 */
contract PreciousMetalsOracleAdapter {
    address public owner;
    
    // Asset symbols: "XAU" (Gold), "XAG" (Silver)
    mapping(string => address) public priceFeeds;
    mapping(string => uint256) public fallbackPrices; // 8 decimals standard

    event PriceFeedUpdated(string indexed asset, address indexed feed);
    event FallbackPriceUpdated(string indexed asset, uint256 price);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        // Default Base/Ethereum Chainlink Mainnet/Sepolia feeds
        // XAU / USD standard 8 decimals
        fallbackPrices["XAU"] = 273550000000; // $2,735.50
        fallbackPrices["XAG"] = 3240000000;   // $32.40
    }

    function setPriceFeed(string calldata asset, address feed) external onlyOwner {
        require(feed != address(0), "Invalid feed");
        priceFeeds[asset] = feed;
        emit PriceFeedUpdated(asset, feed);
    }

    function setFallbackPrice(string calldata asset, uint256 price) external onlyOwner {
        fallbackPrices[asset] = price;
        emit FallbackPriceUpdated(asset, price);
    }

    /**
     * @notice Returns the latest price formatted to 8 decimals
     */
    function getLatestPrice(string memory asset) public view returns (uint256 price, uint256 updatedAt) {
        address feed = priceFeeds[asset];
        if (feed != address(0)) {
            try AggregatorV3Interface(feed).latestRoundData() returns (
                uint80,
                int256 answer,
                uint256,
                uint256 timestamp,
                uint80
            ) {
                if (answer > 0 && timestamp > 0) {
                    uint8 decimals = AggregatorV3Interface(feed).decimals();
                    if (decimals == 8) {
                        return (uint256(answer), timestamp);
                    } else if (decimals < 8) {
                        return (uint256(answer) * (10 ** (8 - decimals)), timestamp);
                    } else {
                        return (uint256(answer) / (10 ** (decimals - 8)), timestamp);
                    }
                }
            } catch {
                // Feed failed, use fallback
            }
        }
        
        uint256 fb = fallbackPrices[asset];
        require(fb > 0, "No price available for asset");
        return (fb, block.timestamp);
    }

    /**
     * @notice Computes total USD value (8 decimals) of an asset amount
     * @param asset Asset identifier ("XAU" or "XAG")
     * @param amount Asset amount in standard unit (with 18 decimals)
     */
    function calculateAssetValueUSD(string memory asset, uint256 amount) external view returns (uint256 valueUSD) {
        (uint256 price, ) = getLatestPrice(asset);
        // value = (amount * price) / 1e18 (result in 8 decimals)
        return (amount * price) / 1e18;
    }
}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AgentMicroServiceOracle
 * @notice Monetización on-chain de micro-servicios, heartbeats y atestaciones en Base Sepolia
 */
contract AgentMicroServiceOracle {
    address public immutable agent;
    uint256 public queryFee;
    uint256 public totalEarned;

    struct Heartbeat {
        bytes32 stateHash;
        uint256 timestamp;
        uint256 blockNumber;
        bool isAlive;
    }

    struct AttestationTask {
        address requester;
        string dataUri;
        uint256 reward;
        bool fulfilled;
        bytes32 resultHash;
    }

    Heartbeat public latestHeartbeat;
    uint256 public taskCounter;
    mapping(uint256 => AttestationTask) public tasks;

    event HeartbeatUpdated(bytes32 indexed stateHash, uint256 timestamp, uint256 blockNumber);
    event TaskRequested(uint256 indexed taskId, address indexed requester, uint256 reward);
    event TaskFulfilled(uint256 indexed taskId, bytes32 resultHash);
    event EarningsWithdrawn(address indexed agent, uint256 amount);

    modifier onlyAgent() {
        require(msg.sender == agent, "Solo agente operador");
        _;
    }

    constructor(uint256 _initialQueryFee) {
        agent = msg.sender;
        queryFee = _initialQueryFee;
    }

    function postHeartbeat(bytes32 _stateHash) external onlyAgent {
        latestHeartbeat = Heartbeat({
            stateHash: _stateHash,
            timestamp: block.timestamp,
            blockNumber: block.number,
            isAlive: true
        });
        emit HeartbeatUpdated(_stateHash, block.timestamp, block.number);
    }

    function queryHeartbeat() external payable returns (Heartbeat memory) {
        require(msg.value >= queryFee, "Cuota insuficiente");
        totalEarned += msg.value;
        return latestHeartbeat;
    }

    function requestAttestation(string calldata _dataUri) external payable returns (uint256) {
        require(msg.value > 0, "Debe incluir incentivo");
        taskCounter++;
        tasks[taskCounter] = AttestationTask({
            requester: msg.sender,
            dataUri: _dataUri,
            reward: msg.value,
            fulfilled: false,
            resultHash: bytes32(0)
        });
        emit TaskRequested(taskCounter, msg.sender, msg.value);
        return taskCounter;
    }

    function fulfillAttestation(uint256 _taskId, bytes32 _resultHash) external onlyAgent {
        AttestationTask storage t = tasks[_taskId];
        require(!t.fulfilled, "Tarea ya completada");
        require(t.reward > 0, "Sin recompensa");

        t.fulfilled = true;
        t.resultHash = _resultHash;
        totalEarned += t.reward;

        emit TaskFulfilled(_taskId, _resultHash);
    }

    function withdrawEarnings() external onlyAgent {
        uint256 balance = address(this).balance;
        require(balance > 0, "Sin balance");
        payable(agent).transfer(balance);
        emit EarningsWithdrawn(agent, balance);
    }

    function setQueryFee(uint256 _newFee) external onlyAgent {
        queryFee = _newFee;
    }

    receive() external payable {
        totalEarned += msg.value;
    }
}

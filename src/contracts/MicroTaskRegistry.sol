// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MicroTaskRegistry
 * @dev Registro inmutable de pruebas de trabajo y datos para el Agente Autnomo 24/7
 * Desplegable en Base Sepolia Testnet (Chain ID 84532)
 */
contract MicroTaskRegistry {
    address public immutable owner;
    uint256 public taskCounter;

    struct TaskRecord {
        uint256 id;
        string taskName;
        string dataHash;
        uint256 timestamp;
        address executor;
    }

    mapping(uint256 => TaskRecord) public tasks;

    event TaskRecorded(
        uint256 indexed id,
        string taskName,
        string dataHash,
        uint256 timestamp,
        address indexed executor
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Solo el agente propietario puede ejecutar");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function recordTask(string calldata taskName, string calldata dataHash) external returns (uint256) {
        taskCounter++;
        tasks[taskCounter] = TaskRecord({
            id: taskCounter,
            taskName: taskName,
            dataHash: dataHash,
            timestamp: block.timestamp,
            executor: msg.sender
        });

        emit TaskRecorded(taskCounter, taskName, dataHash, block.timestamp, msg.sender);
        return taskCounter;
    }

    function getTask(uint256 id) external view returns (TaskRecord memory) {
        require(id > 0 && id <= taskCounter, "Tarea no existe");
        return tasks[id];
    }
}

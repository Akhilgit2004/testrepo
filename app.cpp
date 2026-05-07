#include <iostream>
#include <string>
#include <vector>
// BUG 1: Missing #include <algorithm> here

// ==========================================
// DATA STRUCTURES
// ==========================================

struct ServerNode {
    int server_id;
    std::string hostname;
    std::string status;
    double cpu_usage;
    double ram_usage;
} // BUG 2: Missing semicolon here! This will cause cascade errors.

// ==========================================
// MOCK DATABASE INTERFACE
// ==========================================

class DatabaseConnector {
public:
    DatabaseConnector() {
        std::cout << "[System] Database Connector Initialized.\n";
    }

    void connect() {
        std::cout << "[System] Connecting to mock database cluster...\n";
    }

    void disconnect() {
        std::cout << "[System] Disconnecting from mock database cluster...\n";
    }
};

// ==========================================
// SERVER FLEET MANAGER CLASS
// ==========================================

class ServerFleetManager {
private:
    std::vector<ServerNode> fleet;
    DatabaseConnector db;

public:
    ServerFleetManager() {
        db.connect();
    }

    ~ServerFleetManager() {
        db.disconnect();
    }

    void addServer(int id, std::string host, std::string state, double cpu, double ram) {
        ServerNode new_server = {id, host, state, cpu, ram};
        fleet.push_back(new_server);
        std::cout << "[Fleet] Added server: " << host << "\n";
    }

    void optimizeFleet() {
        std::cout << "[Fleet] Optimizing fleet based on CPU usage...\n";
        
        // This requires <algorithm> which is intentionally missing
        std::sort(fleet.begin(), fleet.end(), [](const ServerNode& a, const ServerNode& b) {
            return a.cpu_usage < b.cpu_usage;
        });

        std::cout << "[Fleet] Fleet optimization complete.\n";
    }

    void printFleetStatus() {
        std::cout << "\n--- CURRENT FLEET STATUS ---\n";
        for (size_t i = 0; i < fleet.size(); i++) {
            std::cout << "ID: " << fleet[i].server_id 
                      << " | Host: " << fleet[i].hostname 
                      << " | Status: " << fleet[i].status 
                      << " | CPU: " << fleet[i].cpu_usage << "%\n";
        }
        std::cout << "----------------------------\n\n";
    }

    int countActiveServers() {
        int active_count = 0;
        
        for (size_t i = 0; i < fleet.size(); i++) {
            if (fleet[i].status == "ONLINE") {
                // BUG 3: Typo! Variable is active_count, not active_cnt
                active_cnt++; 
            }
        }
        
        return active_count;
    }

    void performMaintenanceRoutine() {
        std::cout << "[Maintenance] Starting nightly maintenance routine...\n";
        int active = countActiveServers();
        
        if (active < 2) {
            std::cout << "[Warning] Too few active servers to perform safe rolling restart.\n";
            return;
        }

        std::cout << "[Maintenance] Rolling restart initiated on " << active << " servers.\n";
    }
};

// ==========================================
// MAIN EXECUTION
// ==========================================

int main() {
    std::cout << "Starting Server Fleet Management System v2.0\n";
    std::cout << "===========================================\n";

    ServerFleetManager manager;

    // Simulate pulling servers from a cloud provider
    manager.addServer(101, "prod-web-01", "ONLINE", 45.2, 80.1);
    manager.addServer(102, "prod-web-02", "OFFLINE", 0.0, 0.0);
    manager.addServer(103, "prod-db-01", "ONLINE", 89.5, 95.0);
    manager.addServer(104, "prod-cache-01", "ONLINE", 12.0, 40.5);

    manager.printFleetStatus();
    
    manager.optimizeFleet();
    
    manager.performMaintenanceRoutine();

    return 0;
}
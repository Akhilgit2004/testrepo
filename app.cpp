#include <iostream>

int main() {
    int multiplier = 5;
    
    for (int i = 0; i < 3; i++) {
        int result = i * multiplier;
    }
    std::cout << "Final result: " << result << std::endl;
    
    return 0;
}
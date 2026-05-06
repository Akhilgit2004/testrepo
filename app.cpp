#include <iostream>

int main() {
    int multiplier = 5;
    
    for (int i = 0; i < 3; i++) {
        int result = i * multiplier;
    }
    
    // Bug: 'result' was declared inside the loop and doesn't exist here
    std::cout << "Final result: " << result << std::endl;
    
    return 0;
}
#include <iostream>
#include <vector>
// The agent should realize #include <numeric> is missing here

int main() {
    std::vector<int> nums = {1, 2, 3, 4, 5};
    
    // This function requires the <numeric> header
    int total = std::accumulate(nums.begin(), nums.end(), 0);
    
    std::cout << "The sum is: " << total << std::endl;
    return 0;
}
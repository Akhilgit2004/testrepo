#include <iostream>
#include <vector>

int main() {
    std::vector<int> nums = {1, 2, 3, 4, 5};
    int total = std::accumulate(nums.begin(), nums.end(), 0);
    std::cout << "The sum is: " << total << std::endl;
    return 0;
}
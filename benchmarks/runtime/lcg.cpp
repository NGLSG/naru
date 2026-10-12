#include <cstdint>

std::uint32_t kernel(std::uint32_t n, std::uint32_t seed) {
    std::uint32_t i = 0;
    std::uint32_t state = seed;
    while (i < n) {
        state = state * 1664525u + 1013904223u;
        i = i + 1u;
    }
    return state;
}

int main() { return static_cast<int>(kernel(100000000u, 12345u)); }

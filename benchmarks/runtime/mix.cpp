#include <cstdint>

std::uint32_t kernel(std::uint32_t n, std::uint32_t seed) {
    std::uint32_t i = 0;
    std::uint32_t a = seed;
    std::uint32_t b = 67890;
    while (i < n) {
        a = (a * 1664525u + 1013904223u) ^ b;
        b = (b * 22695477u + 1u) ^ a;
        i = i + 1u;
    }
    return a ^ b;
}

int main() { return static_cast<int>(kernel(100000000u, 12345u)); }

fn kernel(n: u32, seed: u32) -> u32 {
    let mut i: u32 = 0;
    let mut a: u32 = seed;
    let mut b: u32 = 67890;
    while i < n {
        a = a.wrapping_mul(1664525).wrapping_add(1013904223) ^ b;
        b = b.wrapping_mul(22695477).wrapping_add(1) ^ a;
        i = i + 1;
    }
    a ^ b
}

fn main() { std::process::exit(kernel(100000000, 12345) as i32); }

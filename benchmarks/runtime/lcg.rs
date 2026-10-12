fn kernel(n: u32, seed: u32) -> u32 {
    let mut i: u32 = 0;
    let mut state: u32 = seed;
    while i < n {
        state = state.wrapping_mul(1664525).wrapping_add(1013904223);
        i = i + 1;
    }
    state
}

fn main() { std::process::exit(kernel(100000000, 12345) as i32); }

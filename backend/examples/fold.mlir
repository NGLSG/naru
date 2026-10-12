module {
  func.func @main() -> i32 {
    %a = arith.constant 20 : i32
    %b = arith.constant 22 : i32
    %answer = arith.addi %a, %b : i32
    return %answer : i32
  }
}

module {
  %wrong = arith.constant 1 : i32
  "naru_device.store"(%wrong) : (i32) -> ()
}

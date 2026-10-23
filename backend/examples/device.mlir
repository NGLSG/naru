module {
  %tile = "naru_device.load"() : () -> !naru_device.tile<f32>
  %result = "naru_device.activate"(%tile) : (!naru_device.tile<f32>) -> !naru_device.tile<f32>
  "naru_device.store"(%result) : (!naru_device.tile<f32>) -> ()
}

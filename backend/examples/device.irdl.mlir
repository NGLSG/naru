module {
  irdl.dialect @naru_device {
    irdl.type @tile {
      %element = irdl.is f32
      irdl.parameters(element: %element)
    }
    irdl.operation @load {
      %f32 = irdl.is f32
      %tile = irdl.parametric @naru_device::@tile<%f32>
      irdl.results(result: %tile)
    }
    irdl.operation @activate {
      %f32 = irdl.is f32
      %tile = irdl.parametric @naru_device::@tile<%f32>
      irdl.operands(input: %tile)
      irdl.results(result: %tile)
    }
    irdl.operation @store {
      %f32 = irdl.is f32
      %tile = irdl.parametric @naru_device::@tile<%f32>
      irdl.operands(value: %tile)
    }
    irdl.operation @launch {
      %integer = irdl.base "#builtin.integer"
      irdl.attributes { "workgroups" = %integer }
    }
  }
}

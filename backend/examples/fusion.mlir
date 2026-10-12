module {
  func.func @double(%input: memref<16xf32>, %output: memref<16xf32>) {
    %temp = memref.alloc() : memref<16xf32>
    affine.for %i = 0 to 16 {
      %x = affine.load %input[%i] : memref<16xf32>
      %y = arith.addf %x, %x : f32
      affine.store %y, %temp[%i] : memref<16xf32>
    }
    affine.for %i = 0 to 16 {
      %y = affine.load %temp[%i] : memref<16xf32>
      affine.store %y, %output[%i] : memref<16xf32>
    }
    memref.dealloc %temp : memref<16xf32>
    return
  }
}

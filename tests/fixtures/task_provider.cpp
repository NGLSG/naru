#include "../../runtime/coro/tasks.h"
#include <chrono>
#include <thread>
#include <atomic>
namespace { std::atomic<bool> entered{false}, released{false}; }
extern "C" int32_t is_null(void *pointer) { return pointer == nullptr ? 42 : 1; }
extern "C" int32_t hold_frame() {
  entered.store(true,std::memory_order_release);
  while (!released.load(std::memory_order_acquire)) std::this_thread::yield();
  return 42;
}
extern "C" int32_t wait_frame() {
  while (!entered.load(std::memory_order_acquire)) std::this_thread::yield();
  return 0;
}
extern "C" int32_t release_frame() { released.store(true,std::memory_order_release); return 0; }
extern "C" int32_t complete_promise(void *promise) {
  std::thread([promise] {
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
    int32_t answer = 42;
    naru_task_resolve(promise,&answer,sizeof(answer));
  }).detach();
  return 0;
}

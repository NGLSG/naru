#include <algorithm>
#include <condition_variable>
#include <coroutine>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <memory>
#include <mutex>
#include <map>
#include <thread>
#include <unordered_map>
#include <vector>

// No language AST or coroutine state machine lives here. LLVM supplies the
// resume/destroy entry points. This executor owns scheduling and dependency
// handoff, including the race between registering an await and suspending.
namespace {
thread_local bool workerMode = false;
thread_local std::vector<void *> activeFrames;
struct Task {
  void *data, *frame;
  uint8_t *status;
  int64_t *error;
  bool running = false, queued = false, cancelled = false, terminal = false;
  bool disposing = false;
  int32_t terminalState = 0;
  int64_t terminalError = 0;
  bool promise = false;
  bool generator = false;
  void *payload = nullptr;
  int64_t payloadSize = 0;
  int64_t steps = 0;
  std::shared_ptr<Task> dependency;
  std::shared_ptr<Task> nextRequest;
  std::weak_ptr<Task> producer;
  std::vector<std::weak_ptr<Task>> waiters;
  Task(void *data, void *frame, uint8_t *status, int64_t *error)
      : data(data), frame(frame), status(status), error(error) {}
  ~Task() { std::free(data); }
  Task(const Task &) = delete;
};
class Executor {
  std::mutex mutex;
  std::condition_variable changed;
  std::deque<std::shared_ptr<Task>> queue;
  std::unordered_map<void *, std::shared_ptr<Task>> tasks;
  std::vector<std::thread> workers;
  using Clock = std::chrono::steady_clock;
  using Timers = std::multimap<Clock::time_point,std::shared_ptr<Task>>;
  Timers timers;
  std::unordered_map<Task *,Timers::iterator> timerIndex;
  std::thread timerThread;
  bool closing = false, stopping = false;
  void registerTask(const std::shared_ptr<Task> &task) {
    tasks.emplace(task->data,task);
    // Source cleanup may register more work while shutdown is draining.
    // Such work must not remain an unstarted lazy task in the registry.
    if (closing) { task->cancelled = true; enqueue(task); }
  }
  std::shared_ptr<Task> get(void *data) {
    auto found = tasks.find(data);
    if (found == tasks.end()) std::abort();
    return found->second;
  }
  void enqueue(const std::shared_ptr<Task> &task) {
    if (task->queued || task->running || task->terminal || task->disposing || (!task->frame && !task->cancelled)) return;
    if (!task->cancelled && task->dependency && !task->dependency->terminal) return;
    if (!task->cancelled && task->generator && !task->nextRequest) return;
    task->queued = true;
    queue.push_back(task);
    changed.notify_all();
  }
  void publish(const std::shared_ptr<Task> &task) {
    task->terminal = true;
    task->terminalState = *task->status;
    task->terminalError = *task->error;
    if (auto timer = timerIndex.find(task.get()); timer != timerIndex.end()) {
      timers.erase(timer->second); timerIndex.erase(timer);
    }
    if (auto producer = task->producer.lock()) {
      if (producer->nextRequest == task && task->terminalState >= 3) producer->nextRequest.reset();
    }
    if (task->generator) finishNext(task,false);
    task->dependency.reset();
    for (auto &entry : task->waiters) {
      if (auto waiter = entry.lock()) enqueue(waiter);
    }
    task->waiters.clear();
    changed.notify_all();
  }
  void execute(std::unique_lock<std::mutex> &lock, const std::shared_ptr<Task> &task) {
      if (task->terminal || task->running) return;
      task->running = true;
      bool cancel = task->cancelled;
      // Only the thread claiming the frame writes its production state.
      // next() can register a replacement request while this frame runs.
      if (!cancel && task->generator) *task->status = 0;
      activeFrames.push_back(task->data);
      lock.unlock();
      if (cancel && task->frame) std::coroutine_handle<>::from_address(task->frame).destroy();
      else if (cancel) {}
      else std::coroutine_handle<>::from_address(task->frame).resume();
      lock.lock();
      activeFrames.pop_back();
      task->running = false;
      ++task->steps;
      if (cancel) {
        task->frame = nullptr;
        *task->status = 4; *task->error = -1;
        publish(task);
      } else if (*task->status >= 2) {
        publish(task);
      } else if (task->generator && *task->status == 1) {
        finishNext(task,true);
        if (task->cancelled) enqueue(task);
      } else if (task->cancelled || !task->dependency || task->dependency->terminal) {
        enqueue(task);
      }
      changed.notify_all();
  }
  void finishNext(const std::shared_ptr<Task> &task, bool yielded) {
    auto result = task->nextRequest;
    if (!result) return;
    task->nextRequest.reset();
    if (result->terminal) return;
    if (task->terminalState >= 3) {
      *result->status = static_cast<uint8_t>(task->terminalState);
      *result->error = task->terminalError;
    } else {
      *static_cast<uint8_t *>(result->payload) = yielded ? 1 : 0;
      *result->status = 2;
    }
    publish(result);
  }
  void worker() {
    workerMode = true;
    std::unique_lock<std::mutex> lock(mutex);
    for (;;) {
      changed.wait(lock, [&] { return stopping || !queue.empty(); });
      if (stopping) return;
      auto task = queue.front(); queue.pop_front(); task->queued = false;
      execute(lock,task);
    }
  }
  void timerLoop() {
    std::unique_lock<std::mutex> lock(mutex);
    while (!stopping) {
      if (timers.empty()) { changed.wait(lock); continue; }
      auto deadline = timers.begin()->first;
      if (Clock::now() < deadline) { changed.wait_until(lock,deadline); continue; }
      auto task = timers.begin()->second;
      timers.erase(timers.begin()); timerIndex.erase(task.get());
      if (!task->terminal && !task->cancelled) { *task->status = 2; publish(task); }
    }
  }
public:
  Executor() {
    unsigned count = std::min(4u, std::max(2u, std::thread::hardware_concurrency()));
    for (unsigned i = 0; i < count; ++i) workers.emplace_back([this] { worker(); });
    timerThread = std::thread([this] { timerLoop(); });
  }
  ~Executor() {
    {
      std::unique_lock<std::mutex> lock(mutex);
      // Keep workers alive while cancellation executes source cleanups. A
      // parent may destroy/await its child; the registry and await pins remain
      // intact until that dependency is released.
      closing = true;
      for (auto &[data,task] : tasks) {
        if (!task->terminal) { task->cancelled = true; enqueue(task); }
      }
      changed.wait(lock,[&] {
        return std::all_of(tasks.begin(),tasks.end(),[](auto &entry) {
          return entry.second->terminal && !entry.second->running;
        });
      });
      stopping = true;
    }
    changed.notify_all();
    for (auto &worker : workers) worker.join();
    timerThread.join();
    // User cleanups may call back into the executor. Do not hold its lock.
    while (!tasks.empty()) {
      auto task = tasks.begin()->second;
      tasks.erase(task->data);
      if (task->frame) std::coroutine_handle<>::from_address(task->frame).destroy();
    }
  }
  void delay(void *data, uint8_t *status, int64_t *error, int64_t milliseconds) {
    std::lock_guard<std::mutex> lock(mutex);
    auto now = Clock::now();
    auto maximum = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::duration::max()-now.time_since_epoch()).count();
    if (milliseconds < 0 || milliseconds > maximum || tasks.count(data)) std::abort();
    auto task = std::make_shared<Task>(data,nullptr,status,error);
    registerTask(task);
    if (!closing) timerIndex.emplace(task.get(),timers.emplace(now+std::chrono::milliseconds(milliseconds),task));
    changed.notify_all();
  }
  void attach(void *data, void *frame, uint8_t *status, int64_t *error) {
    std::lock_guard<std::mutex> lock(mutex);
    if (!frame || tasks.count(data)) std::abort();
    registerTask(std::make_shared<Task>(data,frame,status,error));
  }
  void promise(void *data, uint8_t *status, int64_t *error, void *payload, int64_t size) {
    std::lock_guard<std::mutex> lock(mutex);
    if (size < 0 || tasks.count(data)) std::abort();
    auto task = std::make_shared<Task>(data,nullptr,status,error);
    task->promise = true; task->payload = payload; task->payloadSize = size;
    registerTask(task);
  }
  void generator(void *data, void *frame, uint8_t *status, int64_t *error, void *payload, int64_t size) {
    std::lock_guard<std::mutex> lock(mutex);
    if (!frame || tasks.count(data)) std::abort();
    auto task = std::make_shared<Task>(data,frame,status,error);
    task->generator = true; task->payload = payload; task->payloadSize = size;
    registerTask(task);
  }
  void next(void *data, void *promiseData, uint8_t *status, int64_t *error, void *payload) {
    std::lock_guard<std::mutex> lock(mutex); auto task = get(data);
    if (!task->generator || tasks.count(promiseData)) std::abort();
    auto result = std::make_shared<Task>(promiseData,nullptr,status,error);
    result->promise = true; result->payload = payload; result->payloadSize = 1;
    registerTask(result);
    if (closing) return;
    if (task->nextRequest) {
      *status = 3; *error = -3; publish(result); return;
    }
    task->nextRequest = result;
    result->dependency = task;
    result->producer = task;
    if (task->terminal) finishNext(task,false);
    else enqueue(task);
  }
  void current(void *data, void *destination, int64_t size) {
    std::lock_guard<std::mutex> lock(mutex); auto task = get(data);
    if (!task->generator || task->running || task->disposing || *task->status != 1 || size != task->payloadSize) std::abort();
    if (size) std::memcpy(destination,task->payload,static_cast<size_t>(size));
  }
  int32_t resolve(void *data, const void *source, int64_t size, int64_t error, bool failed) {
    std::lock_guard<std::mutex> lock(mutex);
    auto found = tasks.find(data);
    if (found == tasks.end()) return 0;
    auto task = found->second;
    if (!task->promise) std::abort();
    if (task->terminal || task->cancelled || task->disposing) return 0;
    if (!failed && size != task->payloadSize) std::abort();
    if (!failed && size) std::memcpy(task->payload,source,static_cast<size_t>(size));
    *task->status = failed ? 3 : 2; *task->error = failed ? error : 0;
    publish(task); return 1;
  }
  void spawn(void *data) {
    std::lock_guard<std::mutex> lock(mutex); enqueue(get(data));
  }
  int32_t prepare(void *parentData, void *childData) {
    std::lock_guard<std::mutex> lock(mutex);
    auto parent = get(parentData), child = get(childData);
    // A dependency cycle is a task failure rather than a worker deadlock.
    for (auto current = child; current; current = current->dependency) {
      if (current == parent) {
        *parent->error = -2;
        return -1;
      }
    }
    parent->dependency = child;
    if (child->terminal) return 0;
    child->waiters.emplace_back(parent);
    enqueue(child);
    return 1;
  }
  void pause(void *data) {
    std::lock_guard<std::mutex> lock(mutex); get(data)->dependency.reset();
  }
  void waitFor(std::unique_lock<std::mutex> &lock, const std::shared_ptr<Task> &task) {
    if (std::find(activeFrames.begin(),activeFrames.end(),task->data) != activeFrames.end()) std::abort();
    enqueue(task);
    while (!task->terminal) {
      if (workerMode && !queue.empty()) {
        auto ready = queue.front(); queue.pop_front(); ready->queued = false;
        execute(lock,ready);
      } else changed.wait(lock);
    }
  }
  int32_t wait(void *data) {
    std::unique_lock<std::mutex> lock(mutex); auto task = get(data);
    waitFor(lock,task); return task->terminalState;
  }
  int32_t waitResult(void *data, void *source, void *destination, int64_t size, bool temporary) {
    std::unique_lock<std::mutex> lock(mutex); auto task = get(data);
    waitFor(lock,task);
    int32_t state = task->terminalState;
    if (state == 2 && size) std::memcpy(destination,source,static_cast<size_t>(size));
    lock.unlock();
    if (temporary) destroy(data);
    return state;
  }
  int32_t awaitStatus(void *data) {
    std::lock_guard<std::mutex> lock(mutex); auto task = get(data);
    return task->dependency ? task->dependency->terminalState : 0;
  }
  int64_t awaitError(void *data) {
    std::lock_guard<std::mutex> lock(mutex); auto task = get(data);
    return task->dependency ? task->dependency->terminalError : -2;
  }
  void awaitResult(void *data, void *source, void *destination, int64_t size) {
    std::lock_guard<std::mutex> lock(mutex); auto task = get(data);
    if (!task->dependency || task->dependency->terminalState != 2) std::abort();
    if (size) std::memcpy(destination,source,static_cast<size_t>(size));
  }
  int32_t status(void *data) {
    std::lock_guard<std::mutex> lock(mutex); auto task = get(data);
    return task->terminalState;
  }
  int64_t error(void *data) {
    std::lock_guard<std::mutex> lock(mutex); auto task = get(data);
    return task->terminalError;
  }
  int64_t steps(void *data) {
    std::lock_guard<std::mutex> lock(mutex); return get(data)->steps;
  }
  int64_t live() { std::lock_guard<std::mutex> lock(mutex); return static_cast<int64_t>(tasks.size()); }
  void cancel(void *data) {
    std::lock_guard<std::mutex> lock(mutex); auto task = get(data);
    if (!task->terminal) { task->cancelled = true; enqueue(task); }
  }
  void destroy(void *data) {
    std::unique_lock<std::mutex> lock(mutex); auto task = get(data);
    if (std::find(activeFrames.begin(),activeFrames.end(),data) != activeFrames.end()) std::abort();
    if (task->disposing) std::abort();
    task->disposing = true;
    // Destruction can be a defer executed by a worker. Cancelling a dormant
    // child locally avoids needing a spare worker just to run its destroy edge.
    task->cancelled = true;
    changed.wait(lock, [&] { return !task->running; });
    void *frame = task->frame; task->frame = nullptr;
    task->running = true;
    lock.unlock();
    if (frame) std::coroutine_handle<>::from_address(frame).destroy();
    lock.lock();
    task->running = false;
    if (!task->terminal) { *task->status = 4; *task->error = -1; publish(task); }
    tasks.erase(data);
    changed.notify_all();
    lock.unlock();
  }
};
Executor &executor() { static Executor value; return value; }
}
extern "C" {
void naru_task_attach(void *data, void *frame, uint8_t *status, int64_t *error) { executor().attach(data,frame,status,error); }
void naru_task_delay(void *data, uint8_t *status, int64_t *error, int64_t milliseconds) { executor().delay(data,status,error,milliseconds); }
void naru_task_promise(void *data, uint8_t *status, int64_t *error, void *payload, int64_t size) { executor().promise(data,status,error,payload,size); }
void naru_async_generator_attach(void *data, void *frame, uint8_t *status, int64_t *error, void *payload, int64_t size) { executor().generator(data,frame,status,error,payload,size); }
void naru_async_generator_next(void *data, void *result, uint8_t *status, int64_t *error, void *payload) { executor().next(data,result,status,error,payload); }
void naru_async_generator_current(void *data, void *destination, int64_t size) { executor().current(data,destination,size); }
int32_t naru_task_resolve(void *data, void *source, int64_t size) { return executor().resolve(data,source,size,0,false); }
int32_t naru_task_reject(void *data, int64_t error) { return executor().resolve(data,nullptr,0,error,true); }
void naru_task_spawn(void *data) { executor().spawn(data); }
int32_t naru_task_prepare(void *parent, void *child) { return executor().prepare(parent,child); }
void naru_task_pause(void *data) { executor().pause(data); }
int32_t naru_task_wait(void *data) { return executor().wait(data); }
int32_t naru_task_wait_result(void *data, void *source, void *destination, int64_t size, int32_t temporary) { return executor().waitResult(data,source,destination,size,temporary != 0); }
int32_t naru_task_await_status(void *data) { return executor().awaitStatus(data); }
int64_t naru_task_await_error(void *data) { return executor().awaitError(data); }
void naru_task_await_result(void *data, void *source, void *destination, int64_t size) { executor().awaitResult(data,source,destination,size); }
int32_t naru_task_status(void *data) { return executor().status(data); }
int64_t naru_task_error(void *data) { return executor().error(data); }
int64_t naru_task_steps(void *data) { return executor().steps(data); }
int64_t naru_task_live() { return executor().live(); }
void naru_task_cancel(void *data) { executor().cancel(data); }
void naru_task_destroy(void *data) { executor().destroy(data); }
}

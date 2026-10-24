#ifndef NARU_TASK_RUNTIME_H
#define NARU_TASK_RUNTIME_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
// Generated code provides the data/status/error/result locations. Producers
// retain their promise until all callbacks stop using its handle. resolve and
// reject return 0 after completion/cancellation and never overwrite a result.
void naru_task_promise(void *data, uint8_t *status, int64_t *error, void *payload, int64_t size);
int32_t naru_task_resolve(void *data, void *source, int64_t size);
int32_t naru_task_reject(void *data, int64_t error);
void naru_task_spawn(void *data);
int32_t naru_task_wait(void *data);
void naru_task_cancel(void *data);
void naru_task_destroy(void *data);
#ifdef __cplusplus
}
#endif
#endif

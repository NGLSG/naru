#pragma once

// Overlay: real spdlog headers plus the helpers DCI cannot describe.
// Vyx still calls spdlog::logger::log through the contract (enum → i32,
// string_view as the probed {ptr,len} aggregate). These helpers only cover
// construction / level / drop (shared_ptr sink + logger lifetime).

#include <spdlog/common.h>
#include <spdlog/details/log_msg.h>
#include <spdlog/formatter.h>
#include <spdlog/logger.h>
#include <spdlog/sinks/sink.h>

/* dci-ownership {
  "dci_default_logger()": {
    "return": "owned"
  },
  "dci_drop_logger(spdlog::logger*)": {
    "parameters": { "0": "move" }
  },
  "dci_logger_log(spdlog::logger*,int,const char*,size_t)": {
    "parameters": { "0": "borrow_mut", "2": "borrow" }
  }
} dci-ownership-end */

spdlog::logger *dci_default_logger();
void dci_drop_logger(spdlog::logger *logger);
// Avoid passing fmt's string_view aggregate across the Windows Vyx ABI.
// spdlog constructs the view on its own side of the boundary.
void dci_logger_log(spdlog::logger *logger, int level, const char *data, size_t size);

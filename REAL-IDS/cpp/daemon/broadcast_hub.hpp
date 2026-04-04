#pragma once

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace real_ids::daemon {

/// One subscriber queue; SSE handler blocks until a line is available.
class SseSubscriber {
 public:
  bool pop_line(std::string& out, std::chrono::milliseconds wait) {
    std::unique_lock<std::mutex> lock(mu_);
    if (closed_) return false;
    if (lines_.empty()) {
      cv_.wait_for(lock, wait, [this] { return closed_ || !lines_.empty(); });
    }
    if (closed_ && lines_.empty()) return false;
    if (lines_.empty()) return false;
    out = std::move(lines_.front());
    lines_.pop_front();
    return true;
  }

  void push(std::string line) {
    std::lock_guard<std::mutex> lock(mu_);
    if (closed_) return;
    lines_.push_back(std::move(line));
    cv_.notify_one();
  }

  void close() {
    std::lock_guard<std::mutex> lock(mu_);
    closed_ = true;
    cv_.notify_all();
  }

 private:
  std::mutex mu_;
  std::condition_variable cv_;
  std::deque<std::string> lines_;
  bool closed_{false};
};

class BroadcastHub {
 public:
  std::shared_ptr<SseSubscriber> subscribe() {
    auto sub = std::make_shared<SseSubscriber>();
    std::lock_guard<std::mutex> lock(mu_);
    subs_.push_back(sub);
    return sub;
  }

  void unsubscribe(const std::shared_ptr<SseSubscriber>& sub) {
    if (!sub) return;
    sub->close();
    std::lock_guard<std::mutex> lock(mu_);
    subs_.erase(std::remove(subs_.begin(), subs_.end(), sub), subs_.end());
  }

  void publish(const std::string& json_one_line) {
    std::vector<std::shared_ptr<SseSubscriber>> copy;
    {
      std::lock_guard<std::mutex> lock(mu_);
      copy = subs_;
    }
    for (const auto& s : copy) {
      if (s) s->push(json_one_line);
    }
  }

  std::size_t subscriber_count() const {
    std::lock_guard<std::mutex> lock(mu_);
    return subs_.size();
  }

 private:
  mutable std::mutex mu_;
  std::vector<std::shared_ptr<SseSubscriber>> subs_;
};

}  // namespace real_ids::daemon

# ------------------------------------------------------------
# src/event_sim/sim.py
# デモ用ユーティリティ（sgsim 本体では未使用）
# ------------------------------------------------------------
# Copyright (c) 2021 Damon Wischik. See LICENSE for permissions.
#
# * Python 3.11 以降の新しい asyncio API に合わせて改訂
# * カスタム EventSimulator には依存せず、標準ループでデモを実行
# ------------------------------------------------------------

import asyncio
import heapq
from typing import Optional


# ------------------------------------------------------------
# キュー実装
# ------------------------------------------------------------
class ProcessorSharingQueue:
    """
    サーバ容量を同時に利用する「公平（processor-sharing）」キュー
    """

    def __init__(self, service_rate: float = 1.0,
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        # `get_running_loop()` はコルーチン内で呼ぶ必要があるので
        # ここでは一旦 None を許容し、後で遅延初期化する
        self._service_rate = service_rate
        self._loop = loop
        self._queue: list[tuple[float, float, asyncio.Future]] = []
        self._work_done = 0.0
        self._last_time = 0.0
        self._done_handle: Optional[asyncio.TimerHandle] = None

    # -------- 内部ユーティリティ --------
    def _ensure_loop(self):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
            self._last_time = self._loop.time()

    def _advance_clock(self) -> float:
        now = self._loop.time()
        if self._queue:
            dt = now - self._last_time
            self._work_done += dt / len(self._queue)
        self._last_time = now
        return now

    def _schedule_next_completion(self):
        if not self._queue:
            self._done_handle = None
            return
        work_target, _, _ = self._queue[0]
        dt = (work_target - self._work_done) * len(self._queue)
        self._done_handle = self._loop.call_later(dt, self._complete_one)

    # -------- パブリック API --------
    def process(self, work: float) -> "asyncio.Future[float]":
        """
        `work`（仕事量）を投入し、完了までの sojourn time を返す Future
        """
        self._ensure_loop()

        now = self._advance_clock()
        fut = self._loop.create_future()
        required_work = work / self._service_rate
        heapq.heappush(self._queue, (self._work_done + required_work, now, fut))

        if self._done_handle:
            self._done_handle.cancel()
        self._schedule_next_completion()
        return fut

    # -------- コールバック --------
    def _complete_one(self):
        self._advance_clock()
        _, start_time, fut = heapq.heappop(self._queue)
        fut.set_result(self._last_time - start_time)
        self._schedule_next_completion()


class FIFOQueue:
    """単純な 1 サーバ FIFO キュー（参考実装）"""

    def __init__(self, service_rate: float = 1.0,
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        self._service_rate = service_rate
        self._loop = loop or asyncio.get_running_loop()
        self._queue: list[tuple[float, asyncio.Future]] = []
        self._done_handle: Optional[asyncio.TimerHandle] = None

    def process(self, work: float) -> "asyncio.Future[float]":
        fut = self._loop.create_future()
        duration = work / self._service_rate
        self._queue.append((duration, fut))

        if self._done_handle is None:
            # サーバがアイドルならすぐサービス開始
            self._done_handle = self._loop.call_later(duration, self._complete_one)

        return fut

    def _complete_one(self):
        duration, fut = self._queue.pop(0)
        fut.set_result(duration)

        if self._queue:
            next_duration, _ = self._queue[0]
            self._done_handle = self._loop.call_later(next_duration, self._complete_one)
        else:
            self._done_handle = None


# ------------------------------------------------------------
# デモコード（標準 asyncio ループで動かす）
# ------------------------------------------------------------
async def _queueing_job(q: ProcessorSharingQueue, work: float, sleep_before: float):
    loop = asyncio.get_running_loop()
    print(f"{loop.time():6.3f}  start job (work={work}, wait={sleep_before})")
    await asyncio.sleep(sleep_before)
    print(f"{loop.time():6.3f}  enqueue job")
    fut = q.process(work)
    await fut
    print(f"{loop.time():6.3f}  done   → sojourn={fut.result():.3f}")


async def _demo_jobs():
    q = ProcessorSharingQueue(service_rate=1.0)
    await asyncio.gather(
        _queueing_job(q, work=4, sleep_before=1),
        _queueing_job(q, work=4, sleep_before=3),
    )


def _run_demo():
    """`python -m src.event_sim.sim` で起動されるデモ"""
    print(">>> Processor-Sharing Queue demo (ctrl-c で終了)\n")
    asyncio.run(_demo_jobs())


if __name__ == "__main__":
    _run_demo()

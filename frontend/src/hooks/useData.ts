import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

type PollOptions<T> = { interval: number; while?: (value: T) => boolean };

export function useData<T>(path: string, poll: number | PollOptions<T> = 0) {
  const interval = typeof poll === "number" ? poll : poll.interval;
  const condition = useRef(typeof poll === "number" ? undefined : poll.while);
  condition.current = typeof poll === "number" ? undefined : poll.while;
  const [result, setResult] = useState<{ path: string; data: T } | null>(null);
  const [failure, setFailure] = useState<{
    path: string;
    message: string;
  } | null>(null);
  const controller = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const reload = useCallback(async () => {
    clearTimeout(timer.current);
    controller.current?.abort();
    if (!path) return;
    const request = new AbortController();
    controller.current = request;
    let value: T | undefined;
    try {
      value = await api<T>(path, { signal: request.signal });
      if (!request.signal.aborted) {
        setResult({ path, data: value });
        setFailure(null);
      }
    } catch (e) {
      if (!request.signal.aborted)
        setFailure({ path, message: (e as Error).message });
    } finally {
      // Schedule after completion so a slow response is never repeatedly aborted
      // by a shorter polling interval. Terminal jobs stop making requests.
      if (
        !request.signal.aborted &&
        interval &&
        (value === undefined || !condition.current || condition.current(value))
      ) {
        timer.current = setTimeout(() => void reload(), interval);
      }
    }
  }, [path, interval]);
  useEffect(() => {
    void reload();
    return () => {
      controller.current?.abort();
      clearTimeout(timer.current);
    };
  }, [reload]);
  return {
    data: result?.path === path ? result.data : null,
    error: failure?.path === path ? failure.message : "",
    reload,
  };
}

export const isActiveJob = (value: { status: string }) =>
  ["queued", "running"].includes(value.status);

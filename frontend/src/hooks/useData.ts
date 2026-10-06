import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

export function useData<T>(path: string, poll = 0) {
  const [result, setResult] = useState<{ path: string; data: T } | null>(null);
  const [failure, setFailure] = useState<{
    path: string;
    message: string;
  } | null>(null);
  const controller = useRef<AbortController | null>(null);
  const reload = useCallback(async () => {
    controller.current?.abort();
    if (!path) return;
    const request = new AbortController();
    controller.current = request;
    try {
      const data = await api<T>(path, { signal: request.signal });
      if (!request.signal.aborted) {
        setResult({ path, data });
        setFailure(null);
      }
    } catch (e) {
      if (!request.signal.aborted)
        setFailure({ path, message: (e as Error).message });
    }
  }, [path]);
  useEffect(() => {
    void reload();
    const timer = poll ? setInterval(reload, poll) : undefined;
    return () => {
      controller.current?.abort();
      clearInterval(timer);
    };
  }, [reload, poll]);
  return {
    data: result?.path === path ? result.data : null,
    error: failure?.path === path ? failure.message : "",
    reload,
  };
}

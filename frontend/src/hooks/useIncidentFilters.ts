import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useDebouncedValue } from "./useDebouncedValue";

const allowed = {
  priority: ["high", "medium", "low"],
  status: [
    "active",
    "open",
    "confirmed",
    "needs_context",
    "dismissed",
    "remediated",
  ],
  category: [
    "configuration",
    "customer_export",
    "internal_operational",
    "public_material",
    "unknown",
  ],
};
type Filter =
  | "q"
  | "priority"
  | "status"
  | "category"
  | "organization"
  | "since";

export function useIncidentFilters() {
  const [params, setParams] = useSearchParams();
  const valid = (key: keyof typeof allowed) =>
    allowed[key].includes(params.get(key) || "") ? params.get(key)! : "";
  const filters = {
    q: (params.get("q") || "").slice(0, 200),
    priority: valid("priority"),
    status: valid("status"),
    category: valid("category"),
    organization: params.get("organization") || "",
    since: /^\d{4}-\d{2}-\d{2}$/.test(params.get("since") || "")
      ? params.get("since")!
      : "",
  };
  const rawOffset = Number(params.get("offset") || 0);
  const offset =
    Number.isSafeInteger(rawOffset) && rawOffset >= 0 && rawOffset <= 1000000
      ? Math.floor(rawOffset / 25) * 25
      : 0;
  const [draft, setDraft] = useState(filters.q);
  const previousUrlQuery = useRef(filters.q);
  const writtenQuery = useRef<string | null>(null);
  const search = useDebouncedValue(draft);
  useEffect(() => {
    if (filters.q !== previousUrlQuery.current) {
      previousUrlQuery.current = filters.q;
      if (writtenQuery.current !== filters.q) {
        setDraft(filters.q);
        writtenQuery.current = null;
        return;
      }
      writtenQuery.current = null;
    }
    if (search !== draft || search === filters.q) return;
    writtenQuery.current = search;
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (search) next.set("q", search);
        else next.delete("q");
        next.delete("offset");
        return next;
      },
      { replace: true },
    );
  }, [draft, search, filters.q, setParams]);
  const query = new URLSearchParams({
    ...filters,
    q: search,
    offset: String(offset),
    limit: "25",
  });
  const urlQuery = new URLSearchParams(
    Object.entries(filters).filter(([, value]) => value),
  );
  if (offset) urlQuery.set("offset", String(offset));
  const canonical = urlQuery.toString();
  useEffect(() => {
    if (params.toString() !== canonical)
      setParams(canonical, { replace: true });
  }, [canonical, params, setParams]);
  function setFilter(key: Filter, value: string) {
    if (key === "q") {
      setDraft(value.slice(0, 200));
      return;
    }
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value) next.set(key, value);
        else next.delete(key);
        next.delete("offset");
        return next;
      },
      { replace: false },
    );
  }
  function setOffset(value: number, replace = false) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value) next.set("offset", String(value));
        else next.delete("offset");
        return next;
      },
      { replace },
    );
  }
  return {
    ...filters,
    q: draft,
    offset,
    query,
    setFilter,
    setOffset,
    clear: () => {
      setDraft("");
      setParams({});
    },
    queuePath: `/incidents${canonical ? `?${canonical}` : ""}`,
  };
}

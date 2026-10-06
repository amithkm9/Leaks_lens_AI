export const date = (value?: string | null) =>
  value
    ? new Date(value).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Not checked yet";
export const label = (value: string) => value.replaceAll("_", " ");

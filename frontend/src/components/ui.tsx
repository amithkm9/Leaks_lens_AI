import * as Dialog from "@radix-ui/react-dialog";
import { FileSearch, LoaderCircle, X } from "lucide-react";
import React, { type ReactNode } from "react";
import { label } from "../lib/format";

export function Badge({ value }: { value: string }) {
  return <span className={`badge ${value}`}>{label(value)}</span>;
}
export function ErrorMessage({ message }: { message: string }) {
  return message ? (
    <div className="notice error" role="alert">
      {message}
    </div>
  ) : null;
}
export function Empty({
  icon = <FileSearch size={32} />,
  title,
  children,
}: {
  icon?: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Button({
  children,
  busy,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button {...props} disabled={props.disabled || busy}>
      {busy ? <LoaderCircle className="spin" size={16} /> : null}
      {children}
    </button>
  );
}
export function Header({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      {action}
    </header>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal">
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <Dialog.Close className="icon-button close" aria-label="Close">
            <X size={20} />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Loading() {
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={20} /> Loading workspace…
    </div>
  );
}

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

type Props = {
  title: string;
  description?: string;
  onClose: () => void;
  /** When true, backdrop click, Escape and the X button are disabled (same as Cancel while submitting). */
  busy?: boolean;
  children: ReactNode;
};

/** Lightweight modal matching EdgePanel / ClassifyForm borders — no Dialog kit. */
export function OverridePanel({ title, description, onClose, busy = false, children }: Props) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const busyRef = useRef(busy);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  useEffect(() => {
    const active = document.activeElement;
    if (active instanceof HTMLElement && active !== document.body) returnTo.current = active;
    panelRef.current?.focus({ preventScroll: true });

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || busyRef.current) return;
      e.preventDefault();
      const opener = returnTo.current;
      onCloseRef.current();
      opener?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const close = () => {
    if (busy) return;
    const opener = returnTo.current;
    onClose();
    opener?.focus();
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-slate-900/40 p-4 pt-[10vh]"
      role="presentation"
      onClick={busy ? undefined : close}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={busy || undefined}
        tabIndex={-1}
        className="flex w-full max-w-md flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm focus:outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-2">
          <div className="flex-1">
            <h2 id={titleId} className="text-sm font-semibold text-slate-900">
              {title}
            </h2>
            {description && <p className="mt-1 text-xs text-slate-600">{description}</p>}
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={close} disabled={busy} aria-label="Close">
            <X className="h-4 w-4" aria-hidden />
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}

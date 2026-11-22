import { ImageOff, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { mediaUrl } from "@/api/client";
import type { Media } from "@/api/types";
import { buttonVariants } from "@/components/ui/button";

const KIND_LABEL: Record<Media["kind"], string> = { screenshot: "Screenshot", frame: "Video frame", image: "Image" };

/** "Video frame at 2.0 s" for frames, "Screenshot 1" otherwise. */
function mediaCaption(media: Media, index: number): string {
  const kind = KIND_LABEL[media.kind] ?? "Media";
  return media.frame_ts != null ? `${kind} at ${media.frame_ts.toFixed(1)} s` : `${kind} ${index + 1}`;
}

/** Intrinsic size only when the API knows it (live media report 0×0), so the browser can reserve space. */
const sizeOf = (m: Media) => (m.width > 0 && m.height > 0 ? { width: m.width, height: m.height } : {});

function Unavailable({ label }: { label: string }) {
  return (
    <div
      role="img"
      aria-label={`${label} (unavailable)`}
      className="flex aspect-video w-full flex-col items-center justify-center gap-1 rounded border border-dashed border-slate-300 bg-white text-xs text-slate-500"
    >
      <ImageOff className="h-4 w-4" aria-hidden />
      Image unavailable
    </div>
  );
}

function Tile({ media, label, failed, onFail, onOpen, open }: {
  media: Media; label: string; failed: boolean; onFail: () => void; onOpen: () => void; open: boolean;
}) {
  return (
    <figure className="flex min-w-0 flex-col gap-1">
      {failed ? (
        <Unavailable label={label} />
      ) : (
        <button
          type="button"
          onClick={onOpen}
          aria-pressed={open}
          aria-label={`Enlarge ${label}`}
          className="block rounded outline-none ring-slate-400 focus-visible:ring-2"
        >
          <img
            src={mediaUrl(media.id)}
            alt={label}
            loading="lazy"
            onError={onFail}
            {...sizeOf(media)}
            className="aspect-video h-auto w-full rounded border border-slate-200 bg-white object-contain"
          />
        </button>
      )}
      <figcaption className="text-xs text-slate-600">{label}</figcaption>
      {media.ocr_text && (
        <p className="line-clamp-2 text-xs text-slate-500" title={media.ocr_text}>
          OCR: {media.ocr_text}
        </p>
      )}
    </figure>
  );
}

/** Screenshots and video frames of one artifact, served by GET /api/media/{id} (synthetic placeholders in mock mode). */
export function MediaGallery({ media }: { media: Media[] }) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [failed, setFailed] = useState<ReadonlySet<string>>(new Set());
  const closeRef = useRef<HTMLButtonElement>(null);
  const openIndex = media.findIndex((m) => m.id === openId);
  const open = openIndex >= 0 && !failed.has(openId!) ? media[openIndex]! : null;

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  if (!media.length) return null;
  const fail = (id: string) => setFailed((prev) => new Set(prev).add(id));

  return (
    <section aria-label="Media" className="mt-3 flex flex-col gap-2">
      <p className="text-xs font-medium text-slate-700">Media ({media.length})</p>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {media.map((m, i) => (
          <li key={m.id}>
            <Tile
              media={m}
              label={mediaCaption(m, i)}
              failed={failed.has(m.id)}
              onFail={() => fail(m.id)}
              open={openId === m.id}
              onOpen={() => setOpenId((cur) => (cur === m.id ? null : m.id))}
            />
          </li>
        ))}
      </ul>
      {open && (
        <figure aria-label={`Enlarged ${mediaCaption(open, openIndex)}`} className="flex flex-col gap-2 rounded-md border border-slate-200 bg-white p-2">
          <div className="flex items-center justify-between gap-2">
            <figcaption className="text-xs font-medium text-slate-700">{mediaCaption(open, openIndex)}</figcaption>
            {/* Plain <button>: the shared Button does not forward refs, and focus moves here on open. */}
            <button
              ref={closeRef}
              type="button"
              onClick={() => setOpenId(null)}
              aria-label="Close enlarged media"
              className={buttonVariants({ variant: "ghost", size: "sm" })}
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
          <img
            src={mediaUrl(open.id)}
            alt={mediaCaption(open, openIndex)}
            onError={() => fail(open.id)}
            {...sizeOf(open)}
            className="h-auto max-h-[70vh] w-full object-contain"
          />
          {open.ocr_text && <p className="text-xs text-slate-600">OCR: {open.ocr_text}</p>}
        </figure>
      )}
    </section>
  );
}

import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const badgeVariants = cva("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap", {
  variants: {
    variant: {
      default: "border-slate-200 bg-slate-100 text-slate-700",
      warning: "border-amber-300 bg-amber-50 text-amber-800",
      success: "border-emerald-300 bg-emerald-50 text-emerald-800",
      danger: "border-red-300 bg-red-50 text-red-800",
      outline: "border-slate-300 bg-white text-slate-700",
    },
  },
  defaultVariants: { variant: "default" },
});

export function Badge({ className, variant, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

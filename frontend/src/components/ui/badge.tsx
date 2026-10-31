import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      neutral: "border-border bg-muted text-muted-foreground",
      buy: "border-bull/40 bg-bull/15 text-bull",
      sell: "border-bear/40 bg-bear/15 text-bear",
      wait: "border-warn/40 bg-warn/10 text-warn",
      info: "border-primary/40 bg-primary/10 text-primary",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export function Badge({ className, variant, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

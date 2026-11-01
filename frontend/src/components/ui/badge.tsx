import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      neutral: "border-border bg-muted text-muted-foreground",
      buy: "border-bull/30 bg-bull/10 text-bull",
      sell: "border-bear/30 bg-bear/10 text-bear",
      wait: "border-warn/30 bg-cta/20 text-warn",
      info: "border-primary/25 bg-primary/10 text-primary",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export function Badge({ className, variant, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

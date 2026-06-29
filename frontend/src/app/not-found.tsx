import { ArrowLeft, Compass } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen mesh-bg flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="size-20 mx-auto rounded-3xl bg-brand-gradient grid place-items-center [background-size:200%_100%] animate-gradient-flow mb-6 shadow-2xl shadow-electric/30">
          <Compass className="size-9 text-white" />
        </div>
        <h1 className="font-display font-bold text-6xl md:text-7xl text-gradient mb-2">404</h1>
        <p className="font-display font-semibold text-xl mb-3">Page not found</p>
        <p className="text-sm text-muted-foreground mb-8">
          The route you're looking for doesn't exist. Let's get you back to the dashboard.
        </p>
        <div className="flex flex-col sm:flex-row gap-2 justify-center">
          <Button asChild variant="gradient">
            <Link href="/dashboard"><ArrowLeft className="size-4" /> Open Dashboard</Link>
          </Button>
          <Button asChild variant="glass">
            <Link href="/">Back to landing</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

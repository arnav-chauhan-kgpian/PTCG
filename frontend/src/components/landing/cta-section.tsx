"use client";
import { motion } from "framer-motion";
import { ArrowRight, Github } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/config/site";

export function CtaSection() {
  return (
    <section className="relative py-24 md:py-32 container">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="relative isolate overflow-hidden rounded-3xl border border-border/40 bg-card/30 backdrop-blur-xl p-10 md:p-16 text-center"
      >
        <div className="absolute inset-0 -z-10 bg-brand-gradient opacity-15 [background-size:200%_100%] animate-gradient-flow" />
        <div className="absolute -top-32 -right-32 -z-10 size-96 rounded-full bg-electric/30 blur-3xl" />
        <div className="absolute -bottom-32 -left-32 -z-10 size-96 rounded-full bg-purple/30 blur-3xl" />
        <div className="grid-bg absolute inset-0 -z-10 opacity-30 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_70%)]" />

        <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight max-w-3xl mx-auto">
          Ready to {" "}
          <span className="text-gradient">train, analyze, and battle?</span>
        </h2>
        <p className="mt-4 text-base md:text-lg text-muted-foreground max-w-2xl mx-auto">
          Open-source, MIT-licensed, ready to run locally or deploy with Docker.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Button asChild variant="gradient" size="xl" className="font-semibold">
            <Link href="/dashboard">Launch the App <ArrowRight className="size-5" /></Link>
          </Button>
          <Button asChild variant="glass" size="xl">
            <a href={siteConfig.links.github} target="_blank" rel="noreferrer">
              <Github className="size-5" />
              Star on GitHub
            </a>
          </Button>
        </div>
      </motion.div>
    </section>
  );
}

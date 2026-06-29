import { ArchitectureSection } from "@/components/landing/architecture-section";
import { CtaSection } from "@/components/landing/cta-section";
import { DemoSection } from "@/components/landing/demo-section";
import { FeatureGrid } from "@/components/landing/feature-grid";
import { LandingFooter } from "@/components/landing/footer";
import { Hero } from "@/components/landing/hero";
import { LandingNav } from "@/components/landing/landing-nav";
import { PerformanceSection } from "@/components/landing/performance-section";
import { Testimonials } from "@/components/landing/testimonials";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <LandingNav />
      <main>
        <Hero />
        <FeatureGrid />
        <ArchitectureSection />
        <PerformanceSection />
        <DemoSection />
        <Testimonials />
        <CtaSection />
      </main>
      <LandingFooter />
    </div>
  );
}

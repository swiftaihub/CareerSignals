import { FinalCta } from "@/components/home/final-cta";
import { HeroSection } from "@/components/home/hero-section";
import { HowItWorksSection } from "@/components/home/how-it-works-section";
import { NoiseToSignalSection } from "@/components/home/noise-to-signal-section";
import { ProductPreviewSection } from "@/components/home/product-preview-section";
import { SuccessOutcomeSection } from "@/components/home/success-outcome-section";
import { TrustSection } from "@/components/home/trust-section";

export default function HomePage() {
  return (
    <main className="overflow-hidden">
      <HeroSection />
      <NoiseToSignalSection />
      <HowItWorksSection />
      <ProductPreviewSection />
      <TrustSection />
      <SuccessOutcomeSection />
      <FinalCta />
    </main>
  );
}

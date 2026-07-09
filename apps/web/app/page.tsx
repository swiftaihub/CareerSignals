import { ArchitectureSection } from "@/components/home/architecture-section";
import { FinalCta } from "@/components/home/final-cta";
import { HeroSection } from "@/components/home/hero-section";
import { TechStackSection } from "@/components/home/tech-stack-section";
import { UseCasesSection } from "@/components/home/use-cases-section";
import { ValueSection } from "@/components/home/value-section";

export default function HomePage() {
  return (
    <main>
      <HeroSection />
      <ValueSection />
      <TechStackSection />
      <ArchitectureSection />
      <UseCasesSection />
      <FinalCta />
    </main>
  );
}

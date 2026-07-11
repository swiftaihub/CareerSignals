import type { ReactNode } from "react";

import { PublicHeader } from "@/components/home/public-header";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return <><PublicHeader />{children}</>;
}

import type { ReactNode } from "react";

import { PublicHeader } from "@/components/home/public-header";
import { getCurrentUser } from "@/lib/auth";

export default async function PublicLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  return <><PublicHeader authenticated={Boolean(user)} />{children}</>;
}

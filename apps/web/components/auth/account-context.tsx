"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { CurrentUser } from "@/lib/types";

const AccountContext = createContext<CurrentUser | null>(null);

export function AccountProvider({ user, children }: { user: CurrentUser; children: ReactNode }) {
  return <AccountContext.Provider value={user}>{children}</AccountContext.Provider>;
}

export function useAccount() {
  return useContext(AccountContext);
}

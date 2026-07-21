import { create } from "zustand";

import type { LoginInput, RegisterInput, User } from "../../entities/auth";
import { tokenStorage } from "../../shared/tokenStorage";
import { authApi } from "./authApi";

type AuthState = {
  user: User | null;
  initialized: boolean;
  loading: boolean;
  initialize: () => Promise<void>;
  login: (input: LoginInput) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
};

let initialization: Promise<void> | null = null;

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  initialized: false,
  loading: false,
  initialize: async () => {
    initialization ??= (async () => {
      if (!tokenStorage.getAccessToken() && !tokenStorage.getRefreshToken()) {
        set({ initialized: true });
        return;
      }
      try {
        const user = await authApi.me();
        set({ user });
      } catch {
        tokenStorage.clear();
        set({ user: null });
      } finally {
        set({ initialized: true });
      }
    })();
    await initialization;
  },
  login: async (input) => {
    set({ loading: true });
    try {
      const result = await authApi.login(input);
      tokenStorage.save(result);
      set({ user: result.user, initialized: true });
    } finally {
      set({ loading: false });
    }
  },
  register: async (input) => {
    set({ loading: true });
    try {
      const result = await authApi.register(input);
      tokenStorage.save(result);
      set({ user: result.user, initialized: true });
    } finally {
      set({ loading: false });
    }
  },
  logout: async () => {
    const refreshToken = tokenStorage.getRefreshToken();
    try {
      if (refreshToken) await authApi.logout(refreshToken);
    } finally {
      tokenStorage.clear();
      set({ user: null, initialized: true });
    }
  },
}));
